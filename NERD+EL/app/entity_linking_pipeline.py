from typing import Any, Dict, List, Optional
from app.contextual_linker import ContextualLinker
from app.entity_type_resolver import EntityTypeResolver


class EntityLinkingPipeline:
    """
    Orquestador del pipeline de NER + Entity Linking.

    Flujo:
        1. Extraer entidades mediante NER.
        2. Generar candidatos Wikidata para todas las menciones.
        3. Realizar un ranking provisional sin utilizar contexto gráfico.
        4. Utilizar los resultados provisionales como contexto.
        5. Realizar un segundo ranking utilizando GraphReasoner.
        6. Aplicar DecisionLayer.
        7. Devolver los resultados finales.

    La arquitectura utiliza dos pasadas para evitar depender de
    contexto QID conocido previamente.
    """

    def __init__(
        self,
        nlp_engine,
        wikidata_client,
        initial_ranker,
        context_ranker,
        decision_layer,
        default_domain="general",
        country_qid=None,
        contextual_linker=None,
        entity_type_resolver=None,
    ):
        self.nlp_engine = nlp_engine
        self.wikidata_client = wikidata_client
        self.initial_ranker = initial_ranker
        self.context_ranker = context_ranker
        self.decision_layer = decision_layer
        self.default_domain = default_domain
        self.country_qid = country_qid
        self.contextual_linker = (
            contextual_linker
            if contextual_linker is not None
                else ContextualLinker()
            )
        self.entity_type_resolver = (
            entity_type_resolver
            if entity_type_resolver is not None
                else EntityTypeResolver()
            )
        

    def analyze(
        self,
        text: str,
        domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ejecuta el pipeline completo sobre un texto.

        Parameters
        ----------
        text:
            Texto de entrada.

        domain:
            Dominio semántico opcional.

        Returns
        -------
        dict
            Resultado estructurado del pipeline.
        """

        if not text or not text.strip():
            return {
                "text": text,
                "domain": domain or self.default_domain,
                "entities": [],
            }

        selected_domain = (
            domain.strip().lower()
            if domain and domain.strip()
                else self.default_domain
        )

        # ---------------------------------------------------------
        # 1. NER
        # ---------------------------------------------------------

        doc = self.nlp_engine.parse(text)

        entities = (
            self.nlp_engine
            .extract_named_entities_from_doc(doc)
        )

        text_relations = (
            self.contextual_linker
            .extract_relations(doc, entities)
        )

        if not entities:
            return {
                "text": text,
                "domain": selected_domain,
                "entities": [],
            }

        # ---------------------------------------------------------
        # 2. Generación de candidatos
        # ---------------------------------------------------------

        entity_data = []

        for index, entity in enumerate(entities):

            raw_label = entity.label_

            normalized_label = self.entity_type_resolver.resolve(
                mention=entity.text,
                raw_label=raw_label,
            )

            candidates = self.wikidata_client.search_candidates(
                entity.text,
                country_qid=self.country_qid
            )

            entity_data.append(
                {
                    "index": index,
                    "mention": entity.text,
                    "label_ner_raw": raw_label, # Etiqueta original de spaCy
                    "label_ner": normalized_label, # Etiqueta normalizada por nuestro sistema
                    "start_char": entity.start_char,
                    "end_char": entity.end_char,
                    "candidates": candidates,
                }
            )

        # ---------------------------------------------------------
        # 3. Primera pasada
        # ---------------------------------------------------------
        # Ranking provisional sin utilizar contexto relacional.

        provisional_results = []

        for item in entity_data:

            ranked = self.initial_ranker.rank_candidates(
                mention=item["mention"],
                candidates=item["candidates"],
                ner_label=item["label_ner"],
                domain=selected_domain,
                context_entities=[],
                country_qid=self.country_qid,
            )

            provisional = ranked[0] if ranked else None

            provisional_results.append(
                {
                    "index": item["index"],
                    "mention": item["mention"],
                    "ranked": ranked,
                    "provisional": provisional,
                }
            )

        # ---------------------------------------------------------
        # 4. Construcción del contexto relacional
        # ---------------------------------------------------------

        provisional_by_index = {
            item["index"]: item["provisional"]
            for item in provisional_results
        }

        context_relations_by_entity = {
            item["index"]: []
            for item in entity_data
        }

        for relation in text_relations:

            source_index = relation["source_index"]
            target_index = relation["target_index"]

            source_provisional = (
                provisional_by_index.get(source_index)
            )

            target_provisional = (
                provisional_by_index.get(target_index)
            )

            if not source_provisional or not target_provisional:
                continue

            source_qid = source_provisional.get("id")
            target_qid = target_provisional.get("id")

            if not source_qid or not target_qid:
                continue

            relation_source = {
                "other_qid": target_qid,
                "relation": relation["relation"],
                "direction": "outgoing",
                "phrase": relation["phrase"],
                "confidence": relation["confidence"],
            }

            relation_target = {
                "other_qid": source_qid,
                "relation": relation["relation"],
                "direction": "incoming",
                "phrase": relation["phrase"],
                "confidence": relation["confidence"],
            }

            context_relations_by_entity[
                source_index
            ].append(relation_source)

            context_relations_by_entity[
                target_index
            ].append(relation_target)


        # ---------------------------------------------------------
        # 5. Construcción del contexto QID
        # ---------------------------------------------------------

        context_qids_by_entity = {}

        for item in provisional_results:

            provisional = item["provisional"]

            if provisional and provisional.get("id"):
                context_qids_by_entity[item["index"]] = [
                    provisional["id"]
                ]
            else:
                context_qids_by_entity[item["index"]] = []


        # ---------------------------------------------------------
        # 6. Segunda pasada
        # ---------------------------------------------------------

        final_results = []

        for item in entity_data:

            current_index = item["index"]

            context_qids = []

            for other_index, qids in context_qids_by_entity.items():

                if other_index == current_index:
                    continue

                context_qids.extend(qids)

            context_qids = list(
                dict.fromkeys(context_qids)
            )

            context_relations = (
                context_relations_by_entity.get(
                    current_index,
                    []
                )
            )

            ranked = self.context_ranker.rank_candidates(
                mention=item["mention"],
                candidates=item["candidates"],
                ner_label=item["label_ner"],
                domain=selected_domain,
                context_entities=context_qids,
                context_relations=context_relations,
                country_qid=self.country_qid,
            )

        # -----------------------------------------------------
        # 6. Decision Layer
        # -----------------------------------------------------

            decision = self.decision_layer.decide(ranked)

            result = {
                "mention": item["mention"],

                # Tipo original de spaCy
                "label_ner_raw": item["label_ner_raw"],
                # Tipo semántico normalizado
                "label_ner": item["label_ner"],
                "start_char": item["start_char"],
                "end_char": item["end_char"],
                "decision": decision.get("decision"),
                "wikidata_id": decision.get("wikidata_id"),
                "wikidata_label": decision.get("label"),
                "wikidata_description": decision.get("description"),
                "score": decision.get("score"),
                "margin": decision.get("margin"),
                "reason": decision.get("reason"),
                "context_qids": context_qids,
                # Muy útil para debugging
                "context_relations": context_relations,
            }

            # Información adicional útil para debugging,
            # evaluación y explicación del sistema.
            if decision.get("candidate"):
                result["candidate"] = decision["candidate"]

            if decision.get("alternatives"):
                result["alternatives"] = decision["alternatives"]

            final_results.append(result)

        # ---------------------------------------------------------
        # 7. Resultado completo
        # ---------------------------------------------------------

        return {
            "text": text,
            "domain": selected_domain,
            "entities": final_results,
        }