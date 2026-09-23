import requests
from typing import Optional, List, Dict

from app.config import DOMAIN_CONSTRAINTS


class WikidataClient:
    """
    Cliente para interactuar con la API de Wikidata.

    Responsabilidades:
    - Generar candidatos mediante wbsearchentities.
    - Recuperar propiedades estructuradas de entidades.
    - Mantener compatibilidad con el antiguo get_entity_claims().
    - Resolver y enlazar menciones a entidades Wikidata.
    """

    def __init__(self):
        self.search_url = "https://www.wikidata.org/w/api.php"

        self.headers = {
            "User-Agent": (
                "NERD_EL_App/2.0.0 "
                "(contacto: frank@example.com) "
                "Python-Requests"
            )
        }

    # ============================================================
    # 1. GENERACIÓN Y ENRIQUECIMIENTO DE CANDIDATOS
    # ============================================================

    def search_candidates(
        self,
        query: str,
        country_qid: Optional[str] = None
    ) -> List[Dict]:
            """
            Busca candidatos en Wikidata mediante wbsearchentities
            y los enriquece con propiedades estructuradas.

            Parameters
            ----------
            query : str
                Mención detectada por el NER.

            country_qid : Optional[str]
                QID del país utilizado como contexto geográfico.
                Actualmente no se utiliza como filtro duro.

            Returns
            -------
            List[Dict]
                Lista normalizada y enriquecida de candidatos.

            Cada candidato puede contener:

                {
                    "id": "Q768224",
                    "label": "University of Valladolid",
                    "description": "university in Spain",
                    "aliases": [...],
                    "match": {...},
                    "properties": {
                        "P31": [...],
                        "P279": [...],
                        "P17": [...],
                        "P131": [...],
                        "P159": [...]
                    }
                }
            """

            if not query or not query.strip():
                return []

            params = {
                "action": "wbsearchentities",
                "format": "json",
                "language": "es",
                "search": query.strip(),
                "limit": 5
            }

            try:

                response = requests.get(
                    self.search_url,
                    params=params,
                    headers=self.headers,
                    timeout=4
                )

                response.raise_for_status()

                results = response.json().get(
                    "search",
                    []
                )

                candidates = []

                # Propiedades utilizadas por el ranking semántico,
                # geográfico y de relaciones.
                properties_to_load = [
                    "P31",   # instance of
                    "P279",  # subclass of
                    "P17",   # country
                    "P131",  # located in administrative entity
                    "P159",  # headquarters
                ]

                for item in results:

                    qid = item.get("id")

                    if not qid:
                        continue

                    candidate = {
                        "id": qid,
                        "label": item.get("label"),
                        "description": item.get("description"),

                        "aliases": item.get(
                            "aliases",
                            []
                        ),

                        "match": item.get(
                            "match",
                            {}
                        ),

                        "display": item.get(
                            "display",
                            {}
                        ),

                        "title": item.get(
                            "title"
                        ),

                        "concepturi": item.get(
                            "concepturi"
                        ),
                    }

                    # ----------------------------------------------------
                    # Enriquecimiento estructurado desde Wikidata
                    # ----------------------------------------------------

                    candidate["properties"] = (
                        self.get_entity_properties(
                            qid,
                            properties=properties_to_load
                        )
                    )

                    candidate["superclasses"] = []

                    p31_values = candidate["properties"].get(
                        "P31",
                        []
                    )

                    for p31_qid in p31_values:

                        superclasses = self.get_superclasses(
                            p31_qid,
                            max_depth=2
                        )

                        for superclass in superclasses:

                            if superclass not in candidate["superclasses"]:
                                candidate["superclasses"].append(
                                    superclass
                                )

                    candidates.append(candidate)

                return candidates

            except (
                requests.RequestException,
                ValueError
            ):
                return []
    # ============================================================
    # 2. PROPIEDADES ESTRUCTURADAS DE WIKIDATA
    # ============================================================

    def get_entity_properties(
        self,
        qid: str,
        properties: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """
        Obtiene propiedades estructuradas de una entidad Wikidata.

        Parameters
        ----------
        qid : str
            Identificador Wikidata, por ejemplo Q6496310.

        properties : Optional[List[str]]
            Propiedades que se desean recuperar.

            Ejemplo:
                ["P31", "P17", "P131", "P159", "P452"]

            Si es None, se procesan todas las propiedades cuyo
            valor sea otra entidad Wikidata.

        Returns
        -------
        Dict[str, List[str]]
            Diccionario de propiedades y sus entidades destino.

        Ejemplo:

            {
                "P31": ["Q43229"],
                "P17": ["Q29"],
                "P159": ["Q2807"]
            }
        """

        if not qid or not qid.startswith("Q"):
            return {}

        params = {
            "action": "wbgetentities",
            "format": "json",
            "ids": qid,
            "props": "claims",
            "languages": "es"
        }

        try:
            response = requests.get(
                self.search_url,
                params=params,
                headers=self.headers,
                timeout=4
            )

            response.raise_for_status()

            data = response.json()

            entity_data = (
                data
                .get("entities", {})
                .get(qid, {})
            )

            claims = entity_data.get("claims", {})

            result: Dict[str, List[str]] = {}

            # Si se especifican propiedades, solamente procesamos esas.
            # Si no, procesamos todas las propiedades disponibles.
            selected_properties = (
                set(properties)
                if properties
                else set(claims.keys())
            )

            for property_id in selected_properties:

                property_claims = claims.get(property_id, [])

                values = []

                for claim in property_claims:

                    mainsnak = claim.get("mainsnak", {})

                    datavalue = mainsnak.get("datavalue", {})

                    # Nos interesan únicamente relaciones cuyo destino
                    # sea otra entidad Wikidata.
                    if datavalue.get("type") != "wikibase-entityid":
                        continue

                    value = datavalue.get("value", {})

                    target_qid = value.get("id")

                    if target_qid:
                        values.append(target_qid)

                if values:
                    result[property_id] = list(
                        dict.fromkeys(values)
                    )

            return result

        except (requests.RequestException, ValueError):
            return {}

    # ============================================================
    # 3. JERARQUÍA ONTOLÓGICA
    # ============================================================

    def get_superclasses(
        self,
        qid: str,
        max_depth: int = 2
    ) -> List[str]:
        """
        Recupera las superclases de una entidad/clase Wikidata
        siguiendo relaciones P279 (subclass of).

        Parameters
        ----------
        qid : str
            QID inicial.

        max_depth : int
            Profundidad máxima de exploración.

            1 -> únicamente P279 directo
            2 -> P279 + P279 de las superclases
            3 -> tres niveles, etc.

        Returns
        -------
        List[str]
            Lista de QIDs encontrados en la jerarquía.

        Notes
        -----
        Se utiliza un conjunto visited para evitar ciclos.
        """

        if not qid or not qid.startswith("Q"):
            return []

        if max_depth <= 0:
            return []

        visited = set()
        result = []

        def _visit(
            current_qid: str,
            depth: int
        ) -> None:

            if depth > max_depth:
                return

            if current_qid in visited:
                return

            visited.add(current_qid)

            properties = self.get_entity_properties(
                current_qid,
                properties=["P279"]
            )

            parents = properties.get(
                "P279",
                []
            )

            for parent_qid in parents:

                if parent_qid not in result:
                    result.append(parent_qid)

                _visit(
                    parent_qid,
                    depth + 1
                )

        _visit(
            qid,
            depth=1
        )

        return result

    # ============================================================
    # 3. COMPATIBILIDAD CON LA IMPLEMENTACIÓN ANTERIOR
    # ============================================================

    def get_entity_claims(self, qid: str) -> List[str]:
        """
        Compatibilidad con la implementación anterior.

        Devuelve únicamente los valores de P31 (instance of).

        Esto permite que el código existente de resolve_and_link()
        siga funcionando mientras evolucionamos el sistema.
        """

        properties = self.get_entity_properties(
            qid,
            properties=["P17", "P131", "P31"],
        )


        return properties.get("P31", [])

    # ============================================================
    # 4. ENTITY LINKING
    # ============================================================

    def resolve_and_link(
        self,
        mention: str,
        domain: str,
        full_context: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Genera candidatos y selecciona una entidad Wikidata.

        Esta es la versión actual del resolver. Posteriormente
        sustituiremos su ranking heurístico por un ranking
        multi-señal que incluya evidencia léxica, contextual,
        semántica y de grafo.
        """

        candidates = self.search_candidates(mention)
        candidates["properties"] = properties

        if not candidates:
            return None

        # --------------------------------------------------------
        # Función auxiliar para normalizar la respuesta de Wikidata
        # --------------------------------------------------------

        def extract_info(cand: Dict) -> Dict:

            display = cand.get("display", {})

            label_data = display.get("label", {})
            description_data = display.get("description", {})

            label = (
                label_data.get("value")
                if isinstance(label_data, dict)
                else cand.get("label")
            )

            description = (
                description_data.get("value")
                if isinstance(description_data, dict)
                else cand.get("description")
            )

            return {
                "id": cand.get("id"),
                "label": label or cand.get("label") or mention,
                "description": (
                    description
                    or cand.get("description")
                    or "Sin descripción"
                )
            }

        # --------------------------------------------------------
        # Dominio general
        # --------------------------------------------------------

        if domain == "general" or domain not in DOMAIN_CONSTRAINTS:

            best = extract_info(candidates[0])

            return {
                "id": best["id"],
                "label": best["label"],
                "description": best["description"],
                "score": 1.0,
                "method": "Búsqueda Léxica General"
            }

        # --------------------------------------------------------
        # Dominio específico
        # --------------------------------------------------------

        domain_info = DOMAIN_CONSTRAINTS[domain]

        context_lowercase = (
            full_context.lower()
            if full_context
            else ""
        )

        valid_matches = []

        # --------------------------------------------------------
        # Paso A:
        # Filtrado semántico mediante P31
        # --------------------------------------------------------

        for candidate in candidates:

            info = extract_info(candidate)

            qid = info["id"]

            desc_lowercase = (
                info["description"].lower()
            )

            instance_of_qids = self.get_entity_claims(qid)

            # Comprobamos si alguna clase P31 del candidato
            # pertenece a las clases permitidas por el dominio.
            if any(
                item in instance_of_qids
                for item in domain_info["allowed_classes"]
            ):

                # ------------------------------------------------
                # Evidencia contextual heurística
                # ------------------------------------------------

                context_bonus = 0.0

                if context_lowercase:

                    desc_words = [
                        word
                        for word in (
                            desc_lowercase
                            .replace(",", "")
                            .replace(".", "")
                            .split()
                        )
                        if len(word) > 3
                    ]

                    if any(
                        word in context_lowercase
                        for word in desc_words
                    ):
                        context_bonus = 0.01

                valid_matches.append(
                    {
                        "data": info,
                        "base_score": 0.98,
                        "final_score": (
                            0.98 + context_bonus
                        ),
                        "method": (
                            "Verificación Cruzada por "
                            "Grafo Co-Contextual"
                            if context_bonus > 0
                            else
                            "Verificación Cruzada por "
                            "Grafo (P31 Match)"
                        )
                    }
                )

        # --------------------------------------------------------
        # Seleccionar candidato compatible
        # --------------------------------------------------------

        if valid_matches:

            valid_matches.sort(
                key=lambda x: x["final_score"],
                reverse=True
            )

            best_match = valid_matches[0]

            return {
                "id": best_match["data"]["id"],
                "label": best_match["data"]["label"],
                "description": best_match["data"]["description"],
                "score": min(
                    best_match["final_score"],
                    1.0
                ),
                "method": best_match["method"]
            }

        # --------------------------------------------------------
        # Paso B:
        # Respaldo heurístico por palabras clave
        # --------------------------------------------------------

        for candidate in candidates:

            info = extract_info(candidate)

            desc_lowercase = (
                info["description"].lower()
            )

            if any(
                word in desc_lowercase
                for word in domain_info["keywords"]
            ):

                return {
                    "id": info["id"],
                    "label": info["label"],
                    "description": info["description"],
                    "score": 0.80,
                    "method": (
                        "Alineación por Contexto "
                        "de Descripción"
                    )
                }

        # --------------------------------------------------------
        # Paso C:
        # Fallback
        # --------------------------------------------------------

        fallback = extract_info(candidates[0])

        return {
            "id": fallback["id"],
            "label": fallback["label"],
            "description": fallback["description"],
            "score": 0.40,
            "method": (
                "Asignación por Defecto "
                "(Fuera de Dominio Semántico)"
            )
        }