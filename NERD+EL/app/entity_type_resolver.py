from typing import Optional
import unicodedata


class EntityTypeResolver:

    ORGANIZATION_HEADS = {
        "universidad",
        "instituto",
        "colegio",
        "departamento",
        "facultad",
        "empresa",
        "banco",
        "hospital",
        "fundacion",
        "ministerio",
        "consejo",
        "centro",
        "laboratorio",
        "organizacion",
        "asociacion",
    }

    LOCATION_LABELS = {
        "LOC",
    }

    ORGANIZATION_LABELS = {
        "ORG",
    }

    PERSON_LABELS = {
        "PER",
    }

    def normalize_text(self, text: str) -> str:
        text = text.lower().strip()

        text = unicodedata.normalize(
            "NFD",
            text
        )

        text = "".join(
            ch
            for ch in text
            if unicodedata.category(ch) != "Mn"
        )

        return text

    def resolve(
        self,
        mention: str,
        raw_label: str,
    ) -> str:

        text = self.normalize_text(mention)

        # -------------------------------------------------
        # ORG ya detectado como ORG
        # -------------------------------------------------

        if raw_label in self.ORGANIZATION_LABELS:
            return "ORG"

        # -------------------------------------------------
        # Institución detectada erróneamente como LOC
        # -------------------------------------------------

        first_token = text.split()[0] if text else ""

        if raw_label == "LOC" and first_token in {
            "universidad",
            "instituto",
            "colegio",
            "departamento",
            "facultad",
            "empresa",
            "banco",
            "hospital",
            "fundacion",
            "ministerio",
            "consejo",
            "centro",
            "laboratorio",
        }:
            return "ORG"

        return raw_label