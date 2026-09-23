from fastapi import FastAPI, HTTPException
import traceback

from app.nlp_engine import NLPEngine
from app.wikidata import WikidataClient
from app.graph_reasoner import GraphReasoner
from app.candidate_ranker import CandidateRanker
from app.decision_layer import DecisionLayer
from app.entity_linking_pipeline import EntityLinkingPipeline
from app.schemas import AnalyzeRequest
from app.config import DEFAULT_COUNTRY_QID
from app.entity_type_resolver import EntityTypeResolver


app = FastAPI(
    title="NER + Wikidata Entity Linking API",
    description=(
        "Servicio de reconocimiento de entidades y enlace de entidades a Wikidata."
    ),
    version="1.0.0",
)


# ============================================================
# Componentes del sistema
# ============================================================

nlp_engine = NLPEngine()

wikidata_client = WikidataClient()

graph_reasoner = GraphReasoner(
    wikidata_client
)

initial_ranker = CandidateRanker()

context_ranker = CandidateRanker(
    graph_reasoner=graph_reasoner
)

decision_layer = DecisionLayer(
    min_score=0.50,
    min_margin=0.10
)

entity_type_resolver = EntityTypeResolver()

# ============================================================
# Pipeline principal
# ============================================================

pipeline = EntityLinkingPipeline(
    nlp_engine=nlp_engine,
    wikidata_client=wikidata_client,
    initial_ranker=initial_ranker,
    context_ranker=context_ranker,
    decision_layer=decision_layer,
    default_domain="general",
    country_qid=DEFAULT_COUNTRY_QID,
    entity_type_resolver=entity_type_resolver,
)


# ============================================================
# Endpoints
# ============================================================

@app.get("/")
def root():
    return {
        "service": "NER + Wikidata Entity Linking",
        "status": "ok",
        "version": "1.0.0",
    }


@app.post("/analyze")
def analyze(request: AnalyzeRequest):

    try:
        result = pipeline.analyze(
            text=request.text,
            domain=request.domain,
        )

        return result

    except Exception as exc:
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Error procesando el texto: {exc}",
        )