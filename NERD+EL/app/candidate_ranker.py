from typing import Dict, List, Optional, Any


class CandidateRanker:
    """
    Ranker de candidatos para Entity Linking.

    Combina diferentes señales:

        - similitud léxica
        - compatibilidad NER
        - compatibilidad de dominio
        - similitud contextual
        - coherencia/incoherencia del grafo

    El ranker NO realiza consultas directamente a Wikidata.

    Las consultas de Wikidata son responsabilidad de WikidataClient,
    mientras que la evidencia relacional es proporcionada por
    GraphReasoner.

    graph_score:
        [-1, +1]

        +1  -> fuerte evidencia a favor
         0  -> sin evidencia relevante
        -1  -> fuerte evidencia en contra
    """

    DEFAULT_WEIGHTS = {
        "lexical": 0.20,
        "exact_label": 0.10,
        "ner": 0.10,
        "domain": 0.15,
        "context": 0.15,
        "geography": 0.10,
        "graph": 0.20,
    }

    def __init__(
        self,
        graph_reasoner=None,
        domain_mapper=None,
        weights: Optional[Dict[str, float]] = None
        #_validate_weights=None
    ):
        """
        Inicializa el ranker.

        Parameters
        ----------
        graph_reasoner:
            Instancia de GraphReasoner.

        domain_mapper:
            Instancia de DomainMapper.

        weights:
            Pesos personalizados para las señales.
        """

        self.graph_reasoner = graph_reasoner

        # Importación local para evitar problemas de dependencias
        # durante pruebas aisladas del módulo.
        if domain_mapper is None:
            from app.domain_mapper import DomainMapper
            domain_mapper = DomainMapper()

        self.domain_mapper = domain_mapper

        self.weights = (
            weights.copy()
            if weights is not None
            else self.DEFAULT_WEIGHTS.copy()
        )

        #self._validate_weights()

    # ============================================================
    # PUBLIC API
    # ============================================================

    def rank_candidates(
        self,
        mention: str,
        candidates: List[Dict[str, Any]],
        ner_label: Optional[str] = None,
        domain: str = "general",
        context_entities: Optional[List[str]] = None,
        country_qid: Optional[str] = None,
        context_relations: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Ordena candidatos según las diferentes señales.

        Parameters
        ----------
        mention:
            Texto de la entidad detectada.

        candidates:
            Lista de candidatos procedentes de Wikidata.

        ner_label:
            Etiqueta NER producida por spaCy.

        domain:
            Dominio semántico seleccionado.

        context_entities:
            QIDs de otras entidades relevantes del contexto.

        Returns
        -------
        list
            Candidatos ordenados de mayor a menor score.
        """

        if not candidates:
            return []

        context_entities = context_entities or []
        context_relations = context_relations or []

        ranked = []

        for candidate in candidates:

            lexical_score = self._lexical_score(
                mention,
                candidate
            )

            exact_label_score = self._exact_label_match(
                mention,
                candidate
            )

            ner_score = self._ner_compatibility(
                ner_label,
                candidate
            )

            domain_score = self._domain_compatibility(
                candidate,
                domain
            )

            graph_score, graph_result = self._get_graph_score(
                candidate,
                context_entities
            )

            context_score = self._context_score(
                mention=mention,
                candidate=candidate,
                context_entities=context_entities,
                context_relations=context_relations,
                graph_result=graph_result,
            )

            geography_score = self._geography_score(
            candidate,
            country_qid
            )

            # ----------------------------------------------------
            # Score base sin grafo
            # ----------------------------------------------------

            base_score = (
                lexical_score * self.weights["lexical"]
                + exact_label_score * self.weights["exact_label"]
                + ner_score * self.weights["ner"]
                + domain_score * self.weights["domain"]
                + context_score * self.weights["context"]
                + geography_score * self.weights["geography"]
            )

            # ----------------------------------------------------
            # El grafo funciona como ajuste.
            #
            # Esto evita convertir:
            #
            # graph = 0
            #
            # en una contribución artificial de 0.5.
            # ----------------------------------------------------

            graph_adjustment = (
                graph_score * self.weights["graph"]
            )

            final_score = self._normalize(
                base_score + graph_adjustment
            )

            ranked_candidate = {
                "id": candidate.get("id"),
                "label": candidate.get("label"),
                "description": candidate.get("description"),
                "score": round(final_score, 4),

                "signals": {
                    "lexical": round(lexical_score, 4),
                    "ner": round(ner_score, 4),
                    "domain": round(domain_score, 4),
                    "context": round(context_score, 4),
                    "geography": round(geography_score, 4),
                    "graph": round(graph_score, 4),
                    "exact_label": round(exact_label_score, 4),
                },

                "graph_evidence": graph_result.get(
                    "evidence", []
                ),

                "graph_negative_evidence": graph_result.get(
                    "negative_evidence", []
                ),

                "graph_positive_score": graph_result.get(
                    "positive_score", 0.0
                ),

                "graph_negative_score": graph_result.get(
                    "negative_score", 0.0
                ),
            }

            ranked.append(ranked_candidate)

        ranked.sort(
            key=lambda candidate: candidate["score"],
            reverse=True
        )

        return ranked

    # ============================================================
    # NORMALIZE TEXT
    # ============================================================

    def _normalize_text(self, text: str) -> str:
        """
        Normaliza texto para comparación léxica.

        - Convierte a minúsculas.
        - Elimina espacios redundantes.
        - Elimina diacríticos.
        - Mantiene caracteres alfanuméricos y espacios.
        """

        if not text:
            return ""

        text = str(text).strip().lower()

        # Eliminar tildes y otros diacríticos.
        import unicodedata

        text = unicodedata.normalize(
            "NFD",
            text
        )

        text = "".join(
            char
            for char in text
            if unicodedata.category(char) != "Mn"
        )

        # Normalizar espacios.
        text = " ".join(text.split())

        return text

    # ============================================================
    # GRAPH
    # ============================================================

    def _get_graph_score(
        self,
        candidate: Dict[str, Any],
        context_entities: List[str]
    ):
        """
        Obtiene la evidencia del GraphReasoner.

        Devuelve:

            graph_score
            graph_result
        """

        if self.graph_reasoner is None:
            return 0.0, {
                "score": 0.0,
                "positive_score": 0.0,
                "negative_score": 0.0,
                "evidence": [],
                "negative_evidence": [],
            }

        candidate_qid = candidate.get("id")

        if not candidate_qid or not context_entities:
            return 0.0, {
                "score": 0.0,
                "positive_score": 0.0,
                "negative_score": 0.0,
                "evidence": [],
                "negative_evidence": [],
            }

        try:
            result = self.graph_reasoner.analyze_candidate(
                candidate_qid,
                context_entities
            )

            graph_score = float(
                result.get("score", 0.0)
            )

            return graph_score, result

        except Exception:
            # El fallo del razonador no debe romper todo
            # el proceso de Entity Linking.
            return 0.0, {
                "score": 0.0,
                "positive_score": 0.0,
                "negative_score": 0.0,
                "evidence": [],
                "negative_evidence": [],
            }

    # ============================================================
    # LEXICAL
    # ============================================================

    def _lexical_score(
        self,
        mention: str,
        candidate: Dict[str, Any]
    ) -> float:
            """
            Calcula similitud léxica entre la mención y un candidato
            de Wikidata.

            Prioridad de las señales:
            1. Coincidencia exacta del match devuelto por Wikidata.
            2. Coincidencia exacta con la etiqueta principal.
            3. Coincidencia exacta con un alias.
            4. Coincidencia parcial.
            5. Similitud basada en tokens.
            """

            mention_norm = self._normalize_text(mention)

            if not mention_norm:
                return 0.0

            # ---------------------------------------------------------
            # 1. Match proporcionado por Wikidata
            # ---------------------------------------------------------

            match = candidate.get("match", {})

            if isinstance(match, dict):

                match_text = self._normalize_text(
                    match.get("text", "")
                )

                match_type = match.get("type")

                if match_text == mention_norm:

                    if match_type == "label":
                        return 1.0

                    if match_type == "alias":
                        return 0.95

                    return 0.90

            # ---------------------------------------------------------
            # 2. Etiqueta principal
            # ---------------------------------------------------------

            label_norm = self._normalize_text(
                candidate.get("label", "")
            )

            if not label_norm:
                return 0.0

            if mention_norm == label_norm:
                return 1.0


            # ---------------------------------------------------------
            # 3. Alias
            # ---------------------------------------------------------

            aliases = candidate.get("aliases", [])

            if isinstance(aliases, list):

                for alias in aliases:

                    alias_norm = self._normalize_text(alias)

                    if alias_norm == mention_norm:
                        return 0.95

            # ---------------------------------------------------------
            # 4. Coincidencia parcial
            # ---------------------------------------------------------

            if mention_norm in label_norm:
                return 0.8

            if label_norm in mention_norm:
                return 0.8

            # ---------------------------------------------------------
            # 5. Similitud basada en tokens
            # ---------------------------------------------------------

            mention_tokens = set(
                mention_norm.split()
            )

            label_tokens = set(
                label_norm.split()
            )

            if not mention_tokens or not label_tokens:
                return 0.0

            intersection = (
                mention_tokens & label_tokens
            )

            union = (
                mention_tokens | label_tokens
            )

            return len(intersection) / len(union)

    def _exact_label_match(
        self,
        mention: str,
        candidate: Dict[str, Any]
    ) -> float:
        """
        Evalúa la coincidencia exacta entre la mención y el nombre
        recuperado por Wikidata.

        Prioridad:
            1. label exacto
            2. match exacto de tipo label
            3. match exacto de tipo alias
        """

        mention_norm = self._normalize_text(
            mention
        )

        if not mention_norm:
            return 0.0

        # ---------------------------------------------------------
        # Label canónico
        # ---------------------------------------------------------

        label_norm = self._normalize_text(
            candidate.get("label", "")
        )

        if mention_norm == label_norm:
            return 1.0

        # ---------------------------------------------------------
        # Match devuelto por Wikidata
        # ---------------------------------------------------------

        match = candidate.get(
            "match",
            {}
        )

        if isinstance(match, dict):

            match_text = self._normalize_text(
                match.get("text", "")
            )

            match_type = match.get("type")

            if match_text == mention_norm:

                if match_type == "label":
                    return 1.0

                if match_type == "alias":
                    return 0.4

            # -----------------------------------------------------
            # Aliases del candidato como respaldo
            # -----------------------------------------------------

        aliases = candidate.get(
            "aliases",
            []
        )

        if isinstance(aliases, list):

            for alias in aliases:

                alias_norm = self._normalize_text(
                    alias
                )

                if alias_norm == mention_norm:
                    return 0.4

        return 0.0

    # ============================================================
    # NER
    # ============================================================

    def _ner_compatibility(
    self,
    ner_label: Optional[str],
    candidate: Dict[str, Any]
    ) -> float:

        if not ner_label:
            return 0.5

        label = self._normalize_text(
            candidate.get("label", "")
        )

        description = self._normalize_text(
            candidate.get("description", "")
        )

        properties = candidate.get(
            "properties",
            {}
        )

        superclasses = candidate.get(
            "superclasses",
            []
        )

        text = f"{label} {description}"

        # =========================================================
        # LOC
        # =========================================================

        if ner_label == "LOC":

            # Lugares físicos / asentamientos
            if any(term in text for term in {
                "municipality",
                "municipio",
                "city",
                "ciudad",
                "human settlement",
                "asentamiento",
                "locality",
                "localidad",
                "town",
                "village",
                "pueblo",
            }):
                return 1.0

            # Divisiones administrativas.
            # Son LOC válidas, pero ligeramente menos específicas
            # cuando el texto no indica explícitamente provincia/región.
            if any(term in text for term in {
                "province",
                "provincia",
                "region",
                "región",
                "autonomous community",
                "comunidad autonoma",
                "country",
                "país",
            }):
                return 0.70

            # Entidades que no representan un lugar físico.
            if any(term in text for term in {
                "electoral district",
                "distrito electoral",
                "family name",
                "surname",
                "apellido",
                "given name",
                "nombre de persona",
            }):
                return 0.05

            return 0.4

        # =========================================================
        # ORG
        # =========================================================

        if ner_label == "ORG":

            if any(term in text for term in {
                "university",
                "universidad",
                "organization",
                "organización",
                "organisation",
                "institution",
                "institución",
                "institute",
                "instituto",
                "college",
                "colegio",
                "department",
                "departamento",
                "faculty",
                "facultad",
                "company",
                "empresa",
                "bank",
                "banco",
                "hospital",
                "foundation",
                "fundación",
                "research",
                "investigación",
            }):
                return 1.0

            return 0.4

        # =========================================================
        # PER
        # =========================================================

        if ner_label == "PER":

            if any(term in text for term in {
                "person",
                "persona",
                "politician",
                "político",
                "scientist",
                "científico",
                "actor",
                "actress",
            }):
                return 1.0

            return 0.3

        return 0.5

    # ============================================================
    # DOMAIN
    # ============================================================

    def _domain_compatibility(
        self,
        candidate: Dict[str, Any],
        domain: str
    ) -> float:
        """
        Delegación de la compatibilidad de dominio al
        DomainMapper.
        """

        return self.domain_mapper.score_candidate(
            candidate=candidate,
            domain=domain
        )


    def _relation_compatibility(
        self,
        candidate: Dict[str, Any],
        relation: Dict[str, Any],
        graph_result: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Comprueba si la relación textual es compatible con
        las propiedades de Wikidata del candidato.
        """

        relation_type = relation.get("relation")
        direction = relation.get("direction")
        other_qid = relation.get("other_qid")

        graph_result = graph_result or {}

        properties = candidate.get(
            "properties",
            {}
        )


        # LOCATION

        if relation_type == "location":

            # Organización -> lugar
            if direction == "outgoing":

                if other_qid in properties.get(
                    "P131",
                    []
                ):
                    return 1.0

                if other_qid in properties.get(
                    "P159",
                    []
                ):
                    return 0.85

                if other_qid in properties.get(
                    "P361",
                    []
                ):
                    return 0.60

                if other_qid in properties.get(
                    "P17",
                    []
                ):
                    return 0.20

                return 0.10

            # Lugar <- organización
            if direction == "incoming":

                evidence = graph_result.get(
                    "evidence",
                    []
                )

                for item in evidence:

                    evidence_type = item.get(
                        "type"
                    )

                    source = item.get(
                        "source"
                    )

                    target = item.get(
                        "target"
                    )

                    if other_qid not in {
                        source,
                        target,
                    }:
                        continue

                    if evidence_type in {
                        "direct_administrative_location",
                        "reverse_administrative_location",
                    }:
                        return 1.0

                    if evidence_type in {
                        "direct_headquarters_location",
                        "reverse_headquarters_location",
                    }:
                        return 0.85

                return 0.20


        # MEMBERSHIP

        if relation_type == "membership":

            if direction == "outgoing":

                for property_id in (
                    "P361",
                    "P463",
                    "P749",
                ):
                    if other_qid in properties.get(
                        property_id,
                        []
                    ):
                        return 1.0

                return 0.10

            if direction == "incoming":

                for property_id in (
                    "P361",
                    "P463",
                    "P749",
                ):
                    if other_qid in properties.get(
                        property_id,
                        []
                    ):
                        return 1.0

                return 0.20


        # COLLABORATION

        if relation_type == "collaboration":

            for property_id in (
                "P463",
                "P710",
                "P1344",
            ):
                if other_qid in properties.get(
                    property_id,
                    []
                ):
                    return 1.0

            # No afirmamos incompatibilidad fuerte:
            # "colaboró con" puede no estar representado
            # directamente en Wikidata.
            return 0.25

        # PARTICIPATION

        if relation_type == "participation":

            for property_id in (
                "P710",
                "P1344",
            ):
                if other_qid in properties.get(
                    property_id,
                    []
                ):
                    return 1.0

            return 0.25
        
        # Relación desconocida
        return 0.25

    # ============================================================
    # CONTEXT
    # ============================================================

    def _context_score(
        self,
        mention: str,
        candidate: Dict[str, Any],
        context_entities: List[str],
        context_relations: Optional[List[Dict[str, Any]]] = None,
        graph_result: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Evalúa la compatibilidad contextual de un candidato.

        Combina:
            - relaciones extraídas del texto
            - propiedades de Wikidata del candidato
            - evidencia del GraphReasoner
        """

        context_entities = context_entities or []
        context_relations = context_relations or []
        graph_result = graph_result or {}

        # Sin contexto externo.
        if not context_entities:
            return 0.5

        # Hay entidades contextuales, pero no una relación textual.
        if not context_relations:
            return 0.25

        scores = []

        for relation in context_relations:

            compatibility = self._relation_compatibility(
                candidate=candidate,
                relation=relation,
                graph_result=graph_result,
            )

            confidence = float(
                relation.get("confidence", 0.5)
            )

            contextual_score = (
                compatibility * confidence
                + 0.25 * (1.0 - confidence)
            )

            scores.append(
                contextual_score
            )

        if not scores:
            return 0.25

        return max(
            0.10,
            min(1.0, max(scores))
        )

    # ============================================================
    # GEOGRAPHY
    # ============================================================

    def _geography_score(
    self,
    candidate: Dict[str, Any],
    country_qid: Optional[str]
    ) -> float:

        properties = candidate.get("properties", {})
        countries = set(properties.get("P17", []))

        if not country_qid:
            return 0.5

        if not countries:
            return 0.5

        if country_qid in countries:
            return 1.0

        return 0.0

    # ============================================================
    # NORMALIZATION
    # ============================================================

    @staticmethod
    def _normalize(value: float) -> float:
        """
        Limita el score final al intervalo [0, 1].
        """

        return max(
            0.0,
            min(1.0, float(value))
        )

    @staticmethod
    def _normalize_text(value: str) -> str:
        """
        Normalización textual básica.
        """

        if not value:
            return ""

        return " ".join(
            value.lower().strip().split()
        )

    # ============================================================
    # VALIDATION
    # ============================================================

    def _validate_weights(self):
        """
        Valida la configuración de pesos.
        """

        expected_keys = set(
            self.DEFAULT_WEIGHTS.keys()
        )

        current_keys = set(
            self.weights.keys()
        )

        if current_keys != expected_keys:
            raise ValueError(
                "Los pesos deben contener exactamente: "
                f"{sorted(expected_keys)}"
            )

        if any(
            value < 0
            for value in self.weights.values()
        ):
            raise ValueError(
                "Los pesos no pueden ser negativos."
            )

        total = sum(
            self.weights.values()
        )

        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"La suma de los pesos debe ser 1.0. "
                f"Valor actual: {total}"
            )
