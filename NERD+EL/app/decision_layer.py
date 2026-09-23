from typing import Any, Dict, List, Optional


class DecisionLayer:
    """
    Capa de decisión para Entity Linking.

    Recibe candidatos previamente ordenados por CandidateRanker
    y determina si una mención debe:

        - LINKED
        - AMBIGUOUS
        - NIL

    La capa no genera candidatos ni calcula señales semánticas.
    Su responsabilidad es únicamente tomar una decisión a partir
    del ranking recibido.
    """

    def __init__(
        self,
        min_score: float = 0.50,
        min_margin: float = 0.10,
    ):
        """
        Parameters
        ----------
        min_score:
            Score mínimo requerido para aceptar un candidato.

        min_margin:
            Diferencia mínima requerida entre el primer y segundo
            candidato para considerar que la decisión es suficientemente
            clara.
        """

        if not 0.0 <= min_score <= 1.0:
            raise ValueError(
                "min_score debe estar entre 0 y 1."
            )

        if not 0.0 <= min_margin <= 1.0:
            raise ValueError(
                "min_margin debe estar entre 0 y 1."
            )

        self.min_score = min_score
        self.min_margin = min_margin

    def decide(
        self,
        ranked_candidates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Toma una lista de candidatos ordenados y produce una decisión.

        Parameters
        ----------
        ranked_candidates:
            Lista de candidatos ordenados de mayor a menor score.

        Returns
        -------
        dict
            Resultado de la decisión.
        """

        if not ranked_candidates:
            return self._nil_result(
                reason="no_candidates"
            )

        top_candidate = ranked_candidates[0]

        top_score = self._safe_score(
            top_candidate
        )

        # --------------------------------------------------------
        # Caso 1: el mejor candidato no alcanza el mínimo
        # --------------------------------------------------------

        if top_score < self.min_score:
            return self._nil_result(
                reason="top_score_below_threshold",
                top_candidate=top_candidate,
            )

        # --------------------------------------------------------
        # Caso 2: solo existe un candidato
        # --------------------------------------------------------

        if len(ranked_candidates) == 1:
            return self._linked_result(
                top_candidate=top_candidate,
                margin=None,
                reason="single_candidate_above_threshold",
            )

        # --------------------------------------------------------
        # Caso 3: existen al menos dos candidatos
        # --------------------------------------------------------

        second_candidate = ranked_candidates[1]

        second_score = self._safe_score(
            second_candidate
        )

        margin = top_score - second_score

        # --------------------------------------------------------
        # Caso 4: diferencia insuficiente
        # --------------------------------------------------------

        if margin < self.min_margin:
            return self._ambiguous_result(
                top_candidate=top_candidate,
                second_candidate=second_candidate,
                margin=margin,
                reason="insufficient_margin",
            )

        # --------------------------------------------------------
        # Caso 5: candidato suficientemente fuerte y separado
        # --------------------------------------------------------

        return self._linked_result(
            top_candidate=top_candidate,
            margin=margin,
            reason="score_and_margin_above_threshold",
        )

    # ============================================================
    # RESULT BUILDERS
    # ============================================================

    def _linked_result(
        self,
        top_candidate: Dict[str, Any],
        margin: Optional[float],
        reason: str,
    ) -> Dict[str, Any]:

        return {
            "decision": "LINKED",
            "wikidata_id": top_candidate.get("id"),
            "label": top_candidate.get("label"),
            "description": top_candidate.get(
                "description"
            ),
            "score": self._safe_score(
                top_candidate
            ),
            "margin": (
                round(margin, 4)
                if margin is not None
                else None
            ),
            "reason": reason,
            "candidate": top_candidate,
        }

    def _ambiguous_result(
        self,
        top_candidate: Dict[str, Any],
        second_candidate: Dict[str, Any],
        margin: float,
        reason: str,
    ) -> Dict[str, Any]:

        return {
            "decision": "AMBIGUOUS",
            "wikidata_id": None,
            "label": None,
            "description": None,
            "score": self._safe_score(
                top_candidate
            ),
            "margin": round(margin, 4),
            "reason": reason,
            "candidate": None,
            "alternatives": [
                top_candidate,
                second_candidate,
            ],
        }

    def _nil_result(
        self,
        reason: str,
        top_candidate: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        return {
            "decision": "NIL",
            "wikidata_id": None,
            "label": None,
            "description": None,
            "score": (
                self._safe_score(top_candidate)
                if top_candidate
                else 0.0
            ),
            "margin": None,
            "reason": reason,
            "candidate": None,
            "alternatives": [],
        }

    # ============================================================
    # UTILITIES
    # ============================================================

    @staticmethod
    def _safe_score(
        candidate: Optional[Dict[str, Any]]
    ) -> float:

        if not candidate:
            return 0.0

        try:
            score = float(
                candidate.get("score", 0.0)
            )
        except (TypeError, ValueError):
            return 0.0

        return max(
            0.0,
            min(1.0, score)
        )