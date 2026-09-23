from app.nlp_engine import NLPEngine
from app.wikidata import WikidataClient
from app.candidate_ranker import CandidateRanker
from app.decision_layer import DecisionLayer
from app.entity_linking_pipeline import EntityLinkingPipeline
from app.graph_reasoner import GraphReasoner
from app.contextual_linker import ContextualLinker
from app.entity_type_resolver import EntityTypeResolver


# ============================================================
# Configuración
# ============================================================

DOMAIN = "educacion"
COUNTRY_QID = "Q29"

nlp = NLPEngine()                       # es_core_news_lg
wikidata = WikidataClient()
graph_reasoner = GraphReasoner(wikidata)

initial_ranker = CandidateRanker(
    graph_reasoner=graph_reasoner
)

context_ranker = CandidateRanker(
    graph_reasoner=graph_reasoner
)

decision_layer = DecisionLayer(
    min_score=0.50,
    min_margin=0.10
)

contextual_linker = ContextualLinker()
entity_type_resolver = EntityTypeResolver()

pipeline = EntityLinkingPipeline(
    nlp_engine=nlp,
    wikidata_client=wikidata,
    initial_ranker=initial_ranker,
    context_ranker=context_ranker,
    decision_layer=decision_layer,
    default_domain=DOMAIN,
    country_qid=COUNTRY_QID,
    contextual_linker=contextual_linker,
    entity_type_resolver=entity_type_resolver,
)

# ============================================================
# Casos de evaluación
#
# gold_qid:
#   QID esperado.
#
# gold_decision:
#   LINKED / AMBIGUOUS / NIL
#
# Para AMBIGUOUS y NIL no es obligatorio indicar gold_qid.
# ============================================================

TEST_CASES = [
    {
        "id": "EDU-01",
        "text": "La Universidad de Valladolid está en Valladolid.",
        "expected": {
            "Universidad de Valladolid": {
                "gold_qid": "Q768224",
                "gold_decision": "LINKED",
            },
            "Valladolid": {
                "gold_qid": "Q8356",
                "gold_decision": "LINKED",
            },
        },
    },
    {
        "id": "EDU-02",
        "text": "La Universidad de Valladolid desarrolla proyectos de investigación.",
        "expected": {
            "Universidad de Valladolid": {
                "gold_qid": "Q768224",
                "gold_decision": "LINKED",
            },
        },
    },
    {
        "id": "EDU-03",
        "text": "La Universidad de Valladolid colaboró con la Universidad de Salamanca.",
        "expected": {
            "Universidad de Valladolid": {
                "gold_qid": "Q768224",
                "gold_decision": "LINKED",
            },
            "Universidad de Salamanca": {
                "gold_qid": "Q308963",
                "gold_decision": "LINKED",
            },
        },
    },
    {
        "id": "EDU-04",
        "text": "La Universidad de Salamanca está ubicada en Salamanca.",
        "expected": {
            "Universidad de Salamanca": {
                "gold_qid": "Q308963",
                "gold_decision": "LINKED",
            },
            "Salamanca": {
                "gold_qid": "Q15695",
                "gold_decision": "LINKED",
            },
        },
    },
    {
        "id": "EDU-05",
        "text": "La Universidad de Valladolid y la Universidad de Salamanca participan en un proyecto de investigación.",
        "expected": {
            "Universidad de Valladolid": {
                "gold_qid": "Q768224",
                "gold_decision": "LINKED",
            },
            "Universidad de Salamanca": {
                "gold_qid": "Q308963",
                "gold_decision": "LINKED",
            },
        },
    },
    {
        "id": "EDU-06",
        "text": "La Universidad de Valladolid tiene un campus en Soria.",
        "expected": {
            "Universidad de Valladolid": {
                "gold_qid": "Q768224",
                "gold_decision": "LINKED",
            },
            "Soria": {
                "gold_qid": "Q12155",
                "gold_decision": "LINKED",
            },
        },
    },
    {
        "id": "EDU-07",
        "text": "El Colegio Universitario de Soria pertenece a la Universidad de Valladolid.",
        "expected": {
            "Colegio Universitario de Soria": {
                "gold_qid": "Q5777208",
                "gold_decision": "LINKED",
            },
            "Universidad de Valladolid": {
                "gold_qid": "Q768224",
                "gold_decision": "LINKED",
            },
        },
    },
    {
        "id": "EDU-08",
        "text": "La Universidad de Valladolid, Instituto Universitario de Urbanística, desarrolla investigación.",
        "expected": {
            "Universidad de Valladolid, Instituto Universitario de Urbanística": {
                "gold_qid": "Q74554486",
                "gold_decision": "LINKED",
            },
        },
    },
    {
        "id": "EDU-09",
        "text": "El Departamento de Historia del Arte de la Universidad de Valladolid desarrolla nuevas investigaciones.",
        "expected": {
            "Departamento de Historia del Arte de la Universidad de Valladolid": {
                "gold_qid": "Q74529331",
                "gold_decision": "LINKED",
            },
        },
    },
    {
        "id": "EDU-10",
        "text": "La Universidad de Salamanca colaboró con la Universidad de Valladolid en un proyecto europeo.",
        "expected": {
            "Universidad de Salamanca": {
                "gold_qid": "Q308963",
                "gold_decision": "LINKED",
            },
            "Universidad de Valladolid": {
                "gold_qid": "Q768224",
                "gold_decision": "LINKED",
            },
        },
    },
    {
        "id": "EDU-11",
        "text": "La Universidad de Castilla Verde inauguró un nuevo campus de investigación.",
        "expected": {
            "Universidad de Castilla Verde": {
                "gold_qid": None,
                "gold_decision": "NIL",
            },
        },
    },
    {
        "id": "EDU-12",
        "text": "La Universidad de Valladolid está vinculada al campus universitario de Soria.",
        "expected": {
            "Universidad de Valladolid": {
                "gold_qid": "Q768224",
                "gold_decision": "LINKED",
            },
            "Soria": {
                "gold_qid": "Q12155",
                "gold_decision": "LINKED",
            },
        },
    },
]


# ============================================================
# Utilidades
# ============================================================

def normalize(text):
    return " ".join(text.lower().strip().split())


def evaluate_entity(entity, expected):
    mention = entity["mention"]

    # Buscar primero coincidencia exacta de la mención.
    exp = expected.get(mention)

    if exp is None:
        normalized_mention = normalize(mention)

        for key, value in expected.items():
            if normalize(key) == normalized_mention:
                exp = value
                break

    if exp is None:
        return {
            "correct": False,
            "status": "UNEXPECTED_ENTITY",
            "gold_qid": None,
            "gold_decision": None,
        }

    predicted_qid = entity.get("wikidata_id")
    predicted_decision = entity.get("decision")

    gold_qid = exp.get("gold_qid")
    gold_decision = exp.get("gold_decision")

    if gold_decision == "LINKED":
        correct = (
            predicted_decision == "LINKED"
            and predicted_qid == gold_qid
        )

    elif gold_decision == "NIL":
        correct = predicted_decision == "NIL"

    elif gold_decision == "AMBIGUOUS":
        correct = predicted_decision == "AMBIGUOUS"

    else:
        correct = False

    return {
        "correct": correct,
        "status": "OK" if correct else "ERROR",
        "gold_qid": gold_qid,
        "gold_decision": gold_decision,
    }


# ============================================================
# Evaluación
# ============================================================

def main():

    print("=" * 100)
    print("EVALUACION NER + ENTITY LINKING")
    print("Dominio: educacion")
    print(f"Pais: España ({COUNTRY_QID})")
    print("=" * 100)

    total_entities = 0
    correct_entities = 0
    linked_expected = 0
    linked_correct = 0
    nil_expected = 0
    nil_correct = 0
    ambiguous_expected = 0
    ambiguous_correct = 0

    detailed_results = []

    for case in TEST_CASES:

        print("\n" + "-" * 100)
        print(f"{case['id']}")
        print(f"Texto: {case['text']}")
        print("-" * 100)

        try:
            result = pipeline.analyze(
                text=case["text"],
                domain=DOMAIN,
            )

        except Exception as exc:
            print(f"ERROR EJECUTANDO PIPELINE: {exc}")
            continue

        expected = case["expected"]
        detected_mentions = set()

        for entity in result.get("entities", []):

            mention = entity["mention"]
            detected_mentions.add(mention)

            evaluation = evaluate_entity(entity, expected)

            total_entities += 1

            if evaluation["correct"]:
                correct_entities += 1

            gold_decision = evaluation["gold_decision"]

            if gold_decision == "LINKED":
                linked_expected += 1
                if evaluation["correct"]:
                    linked_correct += 1

            elif gold_decision == "NIL":
                nil_expected += 1
                if evaluation["correct"]:
                    nil_correct += 1

            elif gold_decision == "AMBIGUOUS":
                ambiguous_expected += 1
                if evaluation["correct"]:
                    ambiguous_correct += 1

            print(
                f"\nMencion: {mention}"
            )

            print(
                f"  NER:       {entity.get('label_ner')}"
            )

            print(
                f"  Prediccion: {entity.get('wikidata_id')} "
                f"-> {entity.get('wikidata_label')}"
            )

            print(
                f"  Decision:   {entity.get('decision')}"
            )

            print(
                f"  Score:      {entity.get('score')}"
            )

            print(
                f"  Margin:     {entity.get('margin')}"
            )

            print(
                f"  Gold QID:   {evaluation['gold_qid']}"
            )

            print(
                f"  Gold dec.:  {evaluation['gold_decision']}"
            )

            print(
                f"  Resultado:  {evaluation['status']}"
            )

            detailed_results.append({
                "case": case["id"],
                "mention": mention,
                "gold_qid": evaluation["gold_qid"],
                "predicted_qid": entity.get("wikidata_id"),
                "gold_decision": evaluation["gold_decision"],
                "predicted_decision": entity.get("decision"),
                "score": entity.get("score"),
                "margin": entity.get("margin"),
                "correct": evaluation["correct"],
            })

        # Comprobar entidades esperadas que no fueron detectadas.
        for expected_mention, expected_info in expected.items():

            found = any(
                normalize(expected_mention) == normalize(m)
                for m in detected_mentions
            )

            if not found:

                print(
                    f"\nMencion esperada NO detectada: "
                    f"{expected_mention}"
                )

                total_entities += 1

                # Si esperábamos NIL pero ni siquiera fue detectada,
                # lo consideramos error del pipeline NER.
                print("  Resultado: ERROR_NER")

                detailed_results.append({
                    "case": case["id"],
                    "mention": expected_mention,
                    "gold_qid": expected_info.get("gold_qid"),
                    "predicted_qid": None,
                    "gold_decision": expected_info.get("gold_decision"),
                    "predicted_decision": None,
                    "score": None,
                    "margin": None,
                    "correct": False,
                })

    # ========================================================
    # Métricas
    # ========================================================

    print("\n")
    print("=" * 100)
    print("RESUMEN DE EVALUACION")
    print("=" * 100)

    accuracy = (
        correct_entities / total_entities
        if total_entities
        else 0.0
    )

    print(f"Entidades evaluadas : {total_entities}")
    print(f"Correctas           : {correct_entities}")
    print(f"Incorrectas         : {total_entities - correct_entities}")
    print(f"Accuracy            : {accuracy:.3f}")

    print("\n--- LINKED ---")

    linked_accuracy = (
        linked_correct / linked_expected
        if linked_expected
        else 0.0
    )

    print(f"Esperadas : {linked_expected}")
    print(f"Correctas : {linked_correct}")
    print(f"Accuracy  : {linked_accuracy:.3f}")

    print("\n--- NIL ---")

    nil_accuracy = (
        nil_correct / nil_expected
        if nil_expected
        else 0.0
    )

    print(f"Esperadas : {nil_expected}")
    print(f"Correctas : {nil_correct}")
    print(f"Accuracy  : {nil_accuracy:.3f}")

    print("\n--- AMBIGUOUS ---")

    ambiguous_accuracy = (
        ambiguous_correct / ambiguous_expected
        if ambiguous_expected
        else 0.0
    )

    print(f"Esperadas : {ambiguous_expected}")
    print(f"Correctas : {ambiguous_correct}")
    print(f"Accuracy  : {ambiguous_accuracy:.3f}")

    print("\n")
    print("=" * 100)
    print("FIN DE LA EVALUACION")
    print("=" * 100)


if __name__ == "__main__":
    main()
