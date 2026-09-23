from typing import Dict, List, Optional, Any


class GraphReasoner:
    """
    Analiza la coherencia entre una entidad candidata y las entidades
    detectadas en el contexto utilizando relaciones de Wikidata.

    El resultado distingue entre:

        - evidencia positiva
        - evidencia negativa
        - score de coherencia

    El módulo NO decide el enlace final.
    """

    RELATION_WEIGHTS = {
        "P17": 0.35,   # country
        "P159": 0.20,  # headquarters location
        "P131": 0.20,  # located in administrative territorial entity
        "P361": 0.15,  # part of
        "P452": 0.05,  # industry
        "P31": 0.05,   # instance of
    }

    NEGATIVE_WEIGHTS = {
        "P17": 0.40,
        "P159": 0.30,
        "P131": 0.25,
    }

    def __init__(self, wikidata_client):
        self.wikidata = wikidata_client

    # ==============================================================
    # PUBLIC API
    # ==============================================================

    def analyze_candidate(
        self,
        candidate_qid: str,
        context_entity_qids: Optional[List[str]] = None,
        max_hops: int = 2
    ) -> Dict[str, Any]:

        if not candidate_qid:
            return self._empty_result()

        context_entity_qids = context_entity_qids or []

        context_entity_qids = [
            qid
            for qid in context_entity_qids
            if qid and qid != candidate_qid
        ]

        if not context_entity_qids:
            return self._empty_result()

        candidate_graph = self._load_relevant_properties(
            candidate_qid
        )

        positive_evidence = []
        negative_evidence = []

        for context_qid in context_entity_qids:

            context_graph = self._load_relevant_properties(
                context_qid
            )

            pair_result = self._compare_entities(
                candidate_qid,
                candidate_graph,
                context_qid,
                context_graph,
                max_hops
            )

            positive_evidence.extend(
                pair_result["positive"]
            )

            negative_evidence.extend(
                pair_result["negative"]
            )

        positive_score = self._aggregate_evidence(
            positive_evidence
        )

        negative_score = self._aggregate_evidence(
            negative_evidence
        )

        graph_score = positive_score - negative_score

        graph_score = max(
            -1.0,
            min(1.0, graph_score)
        )

        return {
            "score": round(graph_score, 4),
            "positive_score": round(positive_score, 4),
            "negative_score": round(negative_score, 4),
            "evidence": positive_evidence,
            "negative_evidence": negative_evidence,
            "candidate_qid": candidate_qid,
            "context_entities": context_entity_qids,
        }

    # ==============================================================
    # WIKIDATA
    # ==============================================================

    def _load_relevant_properties(
        self,
        qid: str
    ) -> Dict[str, List[str]]:

        properties = [
            "P17",
            "P159",
            "P131",
            "P361",
            "P452",
            "P31",
        ]

        return self.wikidata.get_entity_properties(
            qid,
            properties=properties
        )

    # ==============================================================
    # ENTITY COMPARISON
    # ==============================================================

    def _compare_entities(
        self,
        candidate_qid: str,
        candidate_graph: Dict[str, List[str]],
        context_qid: str,
        context_graph: Dict[str, List[str]],
        max_hops: int
    ) -> Dict[str, List[Dict[str, Any]]]:

        positive = []
        negative = []

        # ----------------------------------------------------------
        # 1. Direct relation
        # ----------------------------------------------------------

        direct_positive = self._find_direct_relation(
            candidate_qid,
            candidate_graph,
            context_qid
        )

        positive.extend(direct_positive)

        # ----------------------------------------------------------
        # 1b. Reverse relation
        # ----------------------------------------------------------

        reverse_positive = self._find_reverse_relation(
            candidate_qid,
            context_qid,
            context_graph
        )

        positive.extend(reverse_positive)

        # ----------------------------------------------------------
        # 2. Shared semantic properties
        # ----------------------------------------------------------

        shared_positive = self._find_shared_properties(
            candidate_graph,
            context_graph
        )

        positive.extend(shared_positive)

        # ----------------------------------------------------------
        # 3. Negative geographic evidence
        # ----------------------------------------------------------

        negative.extend(
            self._find_country_mismatch(
                candidate_graph,
                context_graph
            )
        )

        # ----------------------------------------------------------
        # 4. Two-hop relations
        # ----------------------------------------------------------

        if max_hops >= 2:

            two_hop_positive = self._find_two_hop_relation(
                candidate_qid,
                candidate_graph,
                context_qid,
                context_graph
            )

            positive.extend(
                two_hop_positive
            )

        # Eliminar evidencia duplicada.
        positive = self._deduplicate_evidence(
            positive
        )

        negative = self._deduplicate_evidence(
            negative
        )

        return {
            "positive": positive,
            "negative": negative,
        }

    # ==============================================================
    # DIRECT RELATIONS
    # ==============================================================

    def _find_direct_relation(
        self,
        candidate_qid: str,
        candidate_graph: Dict[str, List[str]],
        context_qid: str
    ) -> List[Dict[str, Any]]:

        evidence = []

        for property_id, targets in candidate_graph.items():

            if context_qid not in targets:
                continue

            weight = self.RELATION_WEIGHTS.get(
                property_id,
                0.05
            )

            evidence_type = "direct_relation"

            if property_id == "P131":
                evidence_type = "direct_administrative_location"

            elif property_id == "P159":
                evidence_type = "direct_headquarters_location"

            elif property_id == "P17":
                evidence_type = "direct_country_relation"

            evidence.append({
                "type": evidence_type,
                "property": property_id,
                "source": candidate_qid,
                "target": context_qid,
                "weight": weight,
                "path": [
                    candidate_qid,
                    property_id,
                    context_qid
                ]
            })

        return evidence

    # ==============================================================
    # REVERSE RELATIONS
    # ==============================================================

    def _find_reverse_relation(
        self,
        candidate_qid: str,
        context_qid: str,
        context_graph: Dict[str, List[str]]
    ) -> List[Dict[str, Any]]:

        evidence = []

        for property_id, targets in context_graph.items():

            if candidate_qid not in targets:
                continue

            weight = self.RELATION_WEIGHTS.get(
                property_id,
                0.05
            )

            evidence_type = "reverse_relation"

            if property_id == "P131":
                evidence_type = "reverse_administrative_location"

            elif property_id == "P159":
                evidence_type = "reverse_headquarters_location"

            elif property_id == "P17":
                evidence_type = "reverse_country_relation"

            evidence.append({
                "type": evidence_type,
                "property": property_id,
                "source": context_qid,
                "target": candidate_qid,
                "weight": weight,
                "path": [
                    context_qid,
                    property_id,
                    candidate_qid
                ]
            })

        return evidence

    # ==============================================================
    # SHARED PROPERTIES
    # ==============================================================

    def _find_shared_properties(
        self,
        candidate_graph: Dict[str, List[str]],
        context_graph: Dict[str, List[str]]
    ) -> List[Dict[str, Any]]:

        evidence = []

        # P131 y P159 son relaciones altamente discriminativas.
        # P17 aporta principalmente contexto geográfico general.
        shared_relation_weights = {
            "P131": 0.20,
            "P159": 0.20,
            "P361": 0.15,
            "P17": 0.05,
            "P31": 0.05,
            "P452": 0.05,
        }

        for property_id, weight in shared_relation_weights.items():

            candidate_values = set(
                candidate_graph.get(
                    property_id,
                    []
                )
            )

            context_values = set(
                context_graph.get(
                    property_id,
                    []
                )
            )

            shared_values = (
                candidate_values
                .intersection(context_values)
            )

            for shared_value in shared_values:

                evidence_type = (
                    "shared_country"
                    if property_id == "P17"
                    else "shared_property"
                )

                evidence.append({
                    "type": evidence_type,
                    "property": property_id,
                    "shared_entity": shared_value,
                    "weight": weight,
                    "path": [
                        "candidate",
                        property_id,
                        shared_value,
                        "<-",
                        property_id,
                        "context"
                    ]
                })

        return evidence
    # ==============================================================
    # NEGATIVE EVIDENCE
    # ==============================================================

    def _find_country_mismatch(
        self,
        candidate_graph: Dict[str, List[str]],
        context_graph: Dict[str, List[str]]
    ) -> List[Dict[str, Any]]:

        evidence = []

        candidate_countries = set(
            candidate_graph.get(
                "P17",
                []
            )
        )

        context_countries = set(
            context_graph.get(
                "P17",
                []
            )
        )

        if not candidate_countries:
            return evidence

        if not context_countries:
            return evidence

        if candidate_countries.intersection(
            context_countries
        ):
            return evidence

        evidence.append({
            "type": "country_mismatch",
            "property": "P17",
            "candidate_values": list(
                candidate_countries
            ),
            "context_values": list(
                context_countries
            ),
            "weight": self.NEGATIVE_WEIGHTS["P17"],
        })

        return evidence

    # ==============================================================
    # TWO-HOP RELATIONS
    # ==============================================================

    def _find_two_hop_relation(
        self,
        candidate_qid: str,
        candidate_graph: Dict[str, List[str]],
        context_qid: str,
        context_graph: Dict[str, List[str]]
    ) -> List[Dict[str, Any]]:

        evidence = []

        candidate_targets = set()

        for property_id in [
            "P159",
            "P131",
            "P361",
        ]:
            candidate_targets.update(
                candidate_graph.get(
                    property_id,
                    []
                )
            )

        context_targets = set()

        for property_id in [
            "P159",
            "P131",
            "P361",
        ]:
            context_targets.update(
                context_graph.get(
                    property_id,
                    []
                )
            )

        shared_nodes = (
            candidate_targets
            .intersection(context_targets)
        )

        for shared_node in shared_nodes:

            evidence.append({
                "type": "two_hop_relation",
                "intermediate_entity": shared_node,
                "weight": 0.05,
                "path": [
                    candidate_qid,
                    "relation",
                    shared_node,
                    "<-",
                    "relation",
                    context_qid
                ]
            })

        return evidence

    # ==============================================================
    # EVIDENCE AGGREGATION
    # ==============================================================

    def _aggregate_evidence(
        self,
        evidence: List[Dict[str, Any]]
    ) -> float:

        if not evidence:
            return 0.0

        score = 0.0

        for item in evidence:

            weight = float(
                item.get(
                    "weight",
                    0.0
                )
            )

            score = score + (
                (1.0 - score) * weight
            )

        return min(
            score,
            1.0
        )

    # ==============================================================
    # DEDUPLICATION
    # ==============================================================

    def _deduplicate_evidence(
        self,
        evidence: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:

        unique = []
        seen = set()

        for item in evidence:

            key = (
                item.get("type"),
                item.get("property"),
                item.get("shared_entity"),
                item.get("intermediate_entity"),
            )

            if key in seen:
                continue

            seen.add(key)
            unique.append(item)

        return unique

    # ==============================================================
    # EMPTY RESULT
    # ==============================================================

    def _empty_result(self) -> Dict[str, Any]:

        return {
            "score": 0.0,
            "positive_score": 0.0,
            "negative_score": 0.0,
            "evidence": [],
            "negative_evidence": [],
            "candidate_qid": None,
            "context_entities": [],
        }