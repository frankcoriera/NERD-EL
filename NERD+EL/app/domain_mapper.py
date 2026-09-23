from typing import Dict, List, Set, Optional
import re
import unicodedata


class DomainMapper:
    """
    Mapea dominios de alto nivel a conceptos, términos y categorías
    que pueden aparecer en las descripciones de Wikidata.

    La compatibilidad se calcula mediante tres niveles de evidencia:

    1. Evidencia ontológica:
       - P31 (instance of)
       - P279 (subclass of)

    2. Evidencia léxica:
       - label
       - description
       - aliases
       - domains

    3. Ausencia de evidencia:
       - no se interpreta automáticamente como incompatibilidad.

    El mapper NO decide si un candidato es correcto.
    Únicamente proporciona evidencia de compatibilidad semántica.
    """

    # ==============================================================
    # ONTOLOGICAL CLASSES
    # ==============================================================

    DEFAULT_DOMAIN_CLASSES: Dict[str, Set[str]] = {

        "finanzas": {
            # bank
            "Q197915",
            # financial institution
            "Q193495",
            # financial services
            "Q837171",
        },

        "biomedicina": {
            # hospital
            "Q16917",
            # medical organization
            "Q428563",
            # pharmaceutical company
            "Q484652",
        },

        "tecnologia": {
            # software
            "Q7397",
            # computer
            "Q68",
            # technology company
            "Q783794",
        },

        "educacion": {
            # university
            "Q3918",

            # educational institution
            "Q2385804",

            # educational institution / institute
            "Q875538",

            # school
            "Q9842",

            # higher education institution
            "Q1371037",
        },

        "politica": {
            # political party
            "Q7278",

            # government
            "Q7188",

            # parliament
            "Q35749",
        },

        "geografia": {
            # city
            "Q515",

            # country
            "Q6256",

            # region
            "Q82794",

            # municipality
            "Q484170",

            # province
            "Q134390",
        },

        "forestal": {
            # forest
            "Q4421",

            # ecosystem
            "Q37813",

            # tree
            "Q10884",

            # forest management
            "Q168280",
        },
    }

    # ==============================================================
    # LEXICAL DOMAIN TERMS
    # ==============================================================

    DEFAULT_DOMAIN_TERMS: Dict[str, Set[str]] = {

        "finanzas": {
            "finance",
            "financial",
            "bank",
            "banking",
            "banker",
            "investment",
            "investments",
            "insurance",
            "insurer",
            "credit",
            "securities",
            "stock",
            "banco",
            "banca",
            "finanzas",
            "financiero",
            "financiera",
            "inversion",
            "inversiones",
            "seguros",
            "credito",
            "valores",
        },

        "biomedicina": {
            "medicine",
            "medical",
            "biomedical",
            "health",
            "healthcare",
            "hospital",
            "clinical",
            "pharmaceutical",
            "pharma",
            "drug",
            "medicina",
            "medico",
            "biomedicina",
            "salud",
            "hospital",
            "clinico",
            "farmaceutico",
            "farmaceutica",
            "farmacia",
            "farmaco",
        },

        "tecnologia": {
            "technology",
            "technologies",
            "software",
            "hardware",
            "computer",
            "computing",
            "artificial intelligence",
            "machine learning",
            "data science",
            "information technology",
            "technology company",
            "tecnologia",
            "software",
            "hardware",
            "informatica",
            "computacion",
            "inteligencia artificial",
            "aprendizaje automatico",
            "ciencia de datos",
        },

        "educacion": {
            "education",
            "educational",
            "school",
            "university",
            "college",
            "academy",
            "teacher",
            "student",
            "educacion",
            "educativo",
            "escuela",
            "universidad",
            "colegio",
            "academia",
            "profesor",
            "estudiante",
        },

        "politica": {
            "politics",
            "political",
            "government",
            "governmental",
            "politician",
            "parliament",
            "president",
            "minister",
            "party",
            "politica",
            "politico",
            "gobierno",
            "gubernamental",
            "parlamento",
            "presidente",
            "ministro",
            "partido",
        },

        "geografia": {
            "city",
            "country",
            "region",
            "province",
            "municipality",
            "capital",
            "territory",
            "geography",
            "ciudad",
            "pais",
            "region",
            "provincia",
            "municipio",
            "capital",
            "territorio",
            "geografia",
        },

        "forestal": {
            "forest",
            "forestry",
            "tree",
            "woodland",
            "ecosystem",
            "biodiversity",
            "vegetation",
            "silviculture",
            "forestal",
            "bosque",
            "arbol",
            "ecosistema",
            "biodiversidad",
            "vegetacion",
            "silvicultura",
        },
    }

    def __init__(
        self,
        domain_terms: Optional[Dict[str, Set[str]]] = None,
        domain_classes: Optional[Dict[str, Set[str]]] = None
    ):
        self.domain_terms = (
            domain_terms.copy()
            if domain_terms is not None
            else self.DEFAULT_DOMAIN_TERMS.copy()
        )

        self.domain_classes = (
            domain_classes.copy()
            if domain_classes is not None
            else self.DEFAULT_DOMAIN_CLASSES.copy()
        )

    # ==============================================================
    # PUBLIC API
    # ==============================================================

    def get_terms(
        self,
        domain: str
    ) -> Set[str]:
        """
        Devuelve los términos asociados a un dominio.
        """

        domain_norm = self.normalize(domain)

        return self.domain_terms.get(
            domain_norm,
            set()
        )

    def get_classes(
        self,
        domain: str
    ) -> Set[str]:
        """
        Devuelve las clases Wikidata asociadas a un dominio.
        """

        domain_norm = self.normalize(domain)

        return self.domain_classes.get(
            domain_norm,
            set()
        )

    def score_candidate(
        self,
        candidate: Dict,
        domain: str
    ) -> float:

        if domain == "general":
            return 1.0

        domain = self.normalize(domain)

        allowed_classes = self.DEFAULT_DOMAIN_CLASSES.get(domain, set())

        if not allowed_classes:
            return 0.5

        properties = candidate.get("properties", {}) or {}

        p31 = set(properties.get("P31", []))
        p279 = set(properties.get("P279", []))
        superclasses = set(candidate.get("superclasses", []) or [])

        # ---------------------------------------------------------
        # 1. Evidencia ontológica directa: P31
        # ---------------------------------------------------------
        if p31 & allowed_classes:
            return 1.0

        # ---------------------------------------------------------
        # 2. Evidencia ontológica directa mediante P279
        # ---------------------------------------------------------
        if p279 & allowed_classes:
            return 0.85

        # ---------------------------------------------------------
        # 3. Evidencia ontológica transitive: P31 -> P279*
        # ---------------------------------------------------------
        if superclasses & allowed_classes:
            return 0.80

        # ---------------------------------------------------------
        # 4. Si Wikidata proporciona P31 pero no hay compatibilidad
        #    ontológica, consideramos que existe evidencia negativa.
        #
        #    NO debemos volver al fallback léxico.
        # ---------------------------------------------------------
        if p31:
            return 0.30

        # ---------------------------------------------------------
        # 5. Fallback léxico solamente cuando no tenemos
        #    suficiente información ontológica.
        # ---------------------------------------------------------
        candidate_text = self._candidate_text(candidate)
        if not candidate_text:
            return 0.50

        normalized_text = self._normalize_text(candidate_text)
        domain_terms = self.DEFAULT_DOMAIN_TERMS.get(domain, set())

        if not domain_terms:
            return 0.50

        # Coincidencia exacta con alguno de los términos
        for term in domain_terms:
            if term in normalized_text:
                return 0.70

        # Token overlap
        candidate_tokens = set(normalized_text.split())
        domain_tokens = set()

        for term in domain_terms:
            domain_tokens.update(
                self._normalize_text(term).split()
            )

        if not candidate_tokens or not domain_tokens:
            return 0.50

        overlap = len(candidate_tokens & domain_tokens)
        union = len(candidate_tokens | domain_tokens)

        ratio = overlap / union if union else 0.0

        if ratio >= 0.20:
            return 0.60

        if ratio > 0:
            return 0.55

        return 0.50

    # ==============================================================
    # ONTOLOGY HELPERS
    # ==============================================================

    @staticmethod
    def _normalize_qids(
        values
    ) -> Set[str]:
        """
        Normaliza una colección de QIDs.
        """

        if not values:
            return set()

        if isinstance(values, str):
            values = [values]

        result = set()

        for value in values:

            if not isinstance(value, str):
                continue

            value = value.strip()

            if re.fullmatch(
                r"Q\d+",
                value
            ):
                result.add(value)

        return result

    # ==============================================================
    # LEXICAL SCORING
    # ==============================================================

    def _lexical_score(
        self,
        candidate: Dict,
        domain: str
    ) -> Optional[float]:
        """
        Calcula evidencia léxica.

        Devuelve None cuando no existe suficiente información
        léxica para establecer compatibilidad.
        """

        terms = self.get_terms(domain)

        if not terms:
            return None

        candidate_text = self._candidate_text(
            candidate
        )

        if not candidate_text:
            return None

        candidate_text = self.normalize(
            candidate_text
        )

        # ----------------------------------------------------------
        # Coincidencia exacta
        # ----------------------------------------------------------

        for term in terms:

            term_norm = self.normalize(term)

            if not term_norm:
                continue

            if self._contains_term(
                candidate_text,
                term_norm
            ):
                return 0.7

        # ----------------------------------------------------------
        # Coincidencia parcial por tokens
        # ----------------------------------------------------------

        candidate_tokens = set(
            candidate_text.split()
        )

        domain_tokens = set()

        for term in terms:

            normalized_term = self.normalize(
                term
            )

            domain_tokens.update(
                normalized_term.split()
            )

        if not candidate_tokens or not domain_tokens:
            return None

        overlap = (
            candidate_tokens
            .intersection(domain_tokens)
        )

        if overlap:

            ratio = (
                len(overlap)
                / len(domain_tokens)
            )

            if ratio >= 0.20:
                return 0.6

            return 0.55

        return None

    # ==============================================================
    # CANDIDATE TEXT
    # ==============================================================

    def _candidate_text(
        self,
        candidate: Dict
    ) -> str:

        parts: List[str] = []

        label = candidate.get(
            "label",
            ""
        )

        description = candidate.get(
            "description",
            ""
        )

        aliases = candidate.get(
            "aliases",
            []
        )

        domains = candidate.get(
            "domains",
            []
        )

        if label:
            parts.append(str(label))

        if description:
            parts.append(str(description))

        if aliases:
            parts.extend(
                str(alias)
                for alias in aliases
            )

        if domains:
            parts.extend(
                str(value)
                for value in domains
            )

        return " ".join(parts)

    # ==============================================================
    # TERM MATCHING
    # ==============================================================

    @staticmethod
    def _contains_term(
        text: str,
        term: str
    ) -> bool:

        if " " in term:
            return term in text

        pattern = (
            r"\b"
            + re.escape(term)
            + r"\b"
        )

        return re.search(
            pattern,
            text
        ) is not None

    # ==============================================================
    # NORMALIZATION
    # ==============================================================

    @staticmethod
    def normalize(
        text: str
    ) -> str:

        if not text:
            return ""

        text = str(text).lower().strip()

        text = unicodedata.normalize(
            "NFD",
            text
        )

        text = "".join(
            char
            for char in text
            if unicodedata.category(char) != "Mn"
        )

        text = re.sub(
            r"[^\w\s-]",
            " ",
            text
        )

        text = re.sub(
            r"\s+",
            " ",
            text
        )

        return text.strip()