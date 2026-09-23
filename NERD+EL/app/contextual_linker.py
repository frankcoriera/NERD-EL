from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import unicodedata


@dataclass
class ContextualRelation:
    source_index: int
    target_index: int
    relation: str
    phrase: str
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ContextualLinker:
    """
    Extrae relaciones semánticas simples entre entidades detectadas
    dentro de una misma oración.

    No intenta resolver todavía la relación ontológica exacta de Wikidata.
    Su función es proporcionar contexto semántico al Entity Linking.
    """

    def __init__(self):
        pass

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.lower().strip()

        text = unicodedata.normalize(
            "NFD",
            text
        )

        text = "".join(
            ch for ch in text
            if unicodedata.category(ch) != "Mn"
        )

        return text

    def _lemma_tokens(self, span) -> List[str]:
        tokens = []

        for token in span:
            if token.is_punct:
                continue

            lemma = token.lemma_.strip()

            if not lemma:
                lemma = token.text.strip()

            lemma = self._normalize(lemma)

            if lemma:
                tokens.append(lemma)

        return tokens

    @staticmethod
    def _contains_sequence(
        tokens: List[str],
        sequence: List[str]
    ) -> bool:

        if not sequence:
            return False

        n = len(sequence)

        for i in range(len(tokens) - n + 1):
            if tokens[i:i + n] == sequence:
                return True

        return False

    def _classify_relation(self, tokens: List[str]) -> tuple:
        """
        Devuelve:
            (relation, confidence)
        """

        # ---------------------------------------------------------
        # LOCATION
        # ---------------------------------------------------------

        if (
            "campus" in tokens
            and ("en" in tokens or "de" in tokens)
        ):
            return "location", 0.95

        if (
            "sede" in tokens
            and "en" in tokens
        ):
            return "location", 0.95

        if (
            any(
                lemma in tokens
                for lemma in {
                    "estar",
                    "ubicar",
                    "situar",
                    "localizar"
                }
            )
            and "en" in tokens
        ):
            return "location", 0.90

        if (
            "vincular" in tokens
            and "campus" in tokens
        ):
            return "location", 0.85

        # ---------------------------------------------------------
        # COLLABORATION
        # ---------------------------------------------------------

        if (
            "colaborar" in tokens
            and "con" in tokens
        ):
            return "collaboration", 0.95

        if (
            "cooperar" in tokens
            and "con" in tokens
        ):
            return "collaboration", 0.90

        # ---------------------------------------------------------
        # MEMBERSHIP / BELONGING
        # ---------------------------------------------------------

        if (
            "pertenecer" in tokens
            and ("a" in tokens or "al" in tokens)
        ):
            return "membership", 0.95

        if (
            "formar" in tokens
            and "parte" in tokens
            and "de" in tokens
        ):
            return "membership", 0.90

        if (
            "depender" in tokens
            and "de" in tokens
        ):
            return "membership", 0.85

        # ---------------------------------------------------------
        # PARTICIPATION
        # ---------------------------------------------------------

        if (
            "participar" in tokens
            and "en" in tokens
        ):
            return "participation", 0.80

        return None, 0.0

    def extract_relations(
        self,
        doc,
        entities
    ) -> List[Dict[str, Any]]:

        relations = []

        for i in range(len(entities)):

            source = entities[i]

            for j in range(i + 1, len(entities)):

                target = entities[j]

                # Solamente relaciones dentro de la misma oración.
                if source.sent.start != target.sent.start:
                    continue

                # La mención source debe estar antes que target.
                if source.end > target.start:
                    continue

                between = doc[
                    source.end:target.start
                ]

                if not between:
                    continue

                tokens = self._lemma_tokens(between)

                relation, confidence = self._classify_relation(
                    tokens
                )

                if relation is None:
                    continue

                relations.append(
                    ContextualRelation(
                        source_index=i,
                        target_index=j,
                        relation=relation,
                        phrase=between.text.strip(),
                        confidence=confidence,
                    ).to_dict()
                )

        return relations