# Mapeo estricto de Dominios a IDs de clases raíz en Wikidata para validación cruzada
DOMAIN_CONSTRAINTS = {
    "biomedicina": {
        "allowed_classes": ["Q12136", "Q11173", "Q19080", "Q12140"], # Enfermedad, Compuesto químico, Biomolécula, Medicamento
        "keywords": ["enfermedad", "virus", "síntoma", "fármaco", "tratamiento", "patógeno", "médico"]
    },
    "finanzas": {
        "allowed_classes": ["Q4830453", "Q11635", "Q29271", "Q312068"], # Empresa, Moneda, Banco, Fondo de inversión
        "keywords": ["empresa", "compañía", "banco", "bolsa", "acciones", "corporación", "financiero"]
    },
    "tecnologia": {
        "allowed_classes": ["Q7397", "Q11661", "Q341", "Q4027975"], # Software, TIC, Lenguaje de prog., Computadora
        "keywords": ["software", "programa", "sistema operativo", "computación", "tecnología", "informática"]
    },
        "educacion": {#Utilizado en la aplicación
        "allowed_classes": ["Q3918", "Q2385804", "Q875538", "Q159334", "Q1371037"],
        "keywords": [ "universidad", "universitario", "instituto", "institución educativa", "educación", "educativo", "facultad", "campus", "escuela",
        "colegio", "centro educativo", "educación superior", "educación secundaria", "educación primaria"]
    },
    "general": {
        "allowed_classes": [],
        "keywords": []
    }
}

# ============================================================
# Contexto geográfico
# ============================================================

DEFAULT_COUNTRY = {
    "country_qid": "Q29",
    "country_label": "España",
    "language": "es",
}

DEFAULT_COUNTRY_QID = DEFAULT_COUNTRY["country_qid"]
