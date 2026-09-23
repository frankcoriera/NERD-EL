import spacy

class NLPEngine:
    def __init__(self):
        try:
            self.nlp = spacy.load("es_core_news_lg")
        except OSError:
            raise RuntimeError("Falta el modelo de idioma. Ejecuta: python -m spacy download es_core_news_lg")
        print(f"📦 Modelo cargado: {self.nlp.meta['name']}")
        print(f"🌍 Idioma: {self.nlp.meta['lang']}")
        print(f"📌 Versión del modelo: {self.nlp.meta['version']}")

    def extract_named_entities_from_doc(self, doc) -> list:
        #doc = self.nlp(text)
        # Filtramos categorías de spaCy que representen entidades del mundo real
        valid_labels = ["ORG", "LOC", "PER", "MISC"]
        return [ent for ent in doc.ents if ent.label_ in valid_labels]

    def parse(self, text: str):
        return self.nlp(text)

    def extract_named_entities(self, text: str) -> list:
        doc = self.parse(text)
        return self.extract_named_entities_from_doc(doc)