# NERD+EL
Este repositorio ha sido creado con la finalidad de compartir una propuesta NERD+EL usando Spacy y como base de conocimiento Wikidata.


# 🔗 Semantic Entity Linking Pipeline (`NERD+EL`)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi)
![spaCy](https://img.shields.io/badge/spaCy-es__core__news__lg-09A3D5?logo=spacy)
![Wikidata](https://img.shields.io/badge/Knowledge%20Base-Wikidata-339999?logo=wikidata)
![License](https://img.shields.io/badge/License-MIT-green)


Sistema avanzado de **Reconocimiento de Entidades Nombradas (NER)** y **Entity Linking (EL)** hacia **Wikidata** en español. El sistema resuelve la ambigüedad semántica mediante un **pipeline híbrido en dos pasadas** que combina análisis léxico, compatibilidad ortogonal de tipos, extracción contextual y **razonamiento sobre el grafo de conocimiento**.

---

## 🏛️ Arquitectura del Sistema

El pipeline procesa el texto en dos fases consecutivas (*Two-Pass Execution*):
1. **Pasada 1 (Exploración Local):** Extracción de menciones NER, resolución semántica de tipos (`EntityTypeResolver`) y búsqueda preliminar de candidatos en Wikidata.
2. **Pasada 2 (Razonamiento Contextual):** Construcción de un subgrafo relacional (`GraphReasoner`), scoring multi-señal (`CandidateRanker`) y asignación categórica de estado en la capa de decisión.

```mermaid
graph TD
    A[Texto de entrada] --&gt; B[nlp_engine.py / spaCy]
    B --&gt; C[entity_type_resolver.py]
    C --&gt; D[contextual_linker.py]
    D --&gt; E[wikidata.py / Candidates]
    E --&gt; F[graph_reasoner.py / SPARQL]
    F --&gt; G[candidate_ranker.py / 7 Signals]
    G --&gt; H[decision_layer.py]
    H --&gt; I[LINKED / AMBIGUOUS / NIL]
```

---

## ⚙️ Características Clave

* **Ajuste Semántico Léxico (`EntityTypeResolver`):** Corrige desviaciones del modelo base (ej. reasignando menciones institucionales como `"Universidad de Valladolid"` de `LOC` a `ORG`).
* **Vector de Scoring de 7 Señales (`CandidateRanker`):**
  * Ponderación: **Grafo (20%)**, **Léxica (20%)**, **Dominio (15%)**, **Contexto (15%)**, **Coincidencia Exacta (10%)**, **Compatibilidad NER (10%)** y **Geografía (10%)**.
* **Clasificación Categórica Robusta (`DecisionLayer`):**
  * `LINKED`: Entidad enlazada con alta confianza (`score &gt;= 0.50` y `margin &gt;= 0.10`).
  * `AMBIGUOUS`: Conflicto entre múltiples candidatos cercanos (`margin &lt; 0.10`).
  * `NIL`: Entidad no existente en Wikidata o por debajo del umbral de calidad (`score &lt; 0.50`).
* **Microservicio REST de Alta Velocidad:** Desarrollado sobre **FastAPI** con documentación interactiva Swagger/OpenAPI.

---

## 🚀 Instalación y Despliegue Local

### Requisitos Previos
* **Python 3.10** o superior.
* Conexión a Internet (para la API/SPARQL pública de Wikidata).

### Pasos de Instalación

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/frankcoriera/NERD-EL.git
   cd NERD+EL
   ```

2. **Crear y activar un entorno virtual:**
   ```bash
   python3 -m venv venv

   # En linux:
   source venv/bin/activate

   # En Windows:
   .venv\Scripts\activate
   ```

3. **Instalar dependencias:**
   ```bash
   pip install -r Requirements.txt
   ```

4. **Descargar el modelo en español de spaCy:**
   ```bash
   python -m spacy download es_core_news_lg
   ```

---

## 🧪 Ejecución y Uso de la API

### 1. Iniciar el Servidor REST
Desde la carpeta `NERD+EL/`:
```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
La documentación interactiva estará disponible en:
* **Swagger UI:** `http://localhost:8000/docs`
* **ReDoc:** `http://localhost:8000/redoc`

### 2. Ejemplo de Petición con `curl`
```bash
curl -X "POST" ^  "http://127.0.0.1:8000/analyze" ^ -H "accept: application/json" ^ -H "Content-Type: application/json" ^ -d "{\"text\": \"La Universidad de Valladolid está en Valladolid.\", \"language\": \"es\", \"domain\":\"educacion\"}"
```

---

## 📊 Pruebas y Evaluación Cuantitativa

El proyecto incluye suites de pruebas automáticas para evaluar el desempeño en el dominio educativo:

```bash
# Ejecutar el test específico de dominio educativo (22 entidades)
python -m test.education_test
```

### Resultados de Evaluación en Test Real
* **Accuracy Global:** `72.7%`
* **Precisión en Entidades LINKED:** `83.3%`
* **Precisión en Entidades NIL:** `100.0%`

---

## 📝 Licencia
Este proyecto está bajo la Licencia **MIT**.

```
