from dataclasses import dataclass
from typing import Optional


AUTO_ACCEPT_THRESHOLD = 0.80


@dataclass(frozen=True)
class SeverityDecision:
    predicted_class: Optional[str]
    confidence: Optional[float]
    status: str
    human_review_required: bool
    out_of_scope: bool
    source: str


def decide_severity(
    predicted_class: Optional[str],
    confidence: Optional[float],
    *,
    model_error: bool = False,
) -> SeverityDecision:
    if model_error or predicted_class is None or confidence is None:
        return SeverityDecision(
            predicted_class=predicted_class,
            confidence=confidence,
            status="en_analyse",
            human_review_required=True,
            out_of_scope=False,
            source="indisponible",
        )

    out_of_scope = predicted_class == "hors_sujet"
    requires_review = out_of_scope or confidence < AUTO_ACCEPT_THRESHOLD
    return SeverityDecision(
        predicted_class=predicted_class,
        confidence=confidence,
        status="en_attente_validation" if requires_review else "valide",
        human_review_required=requires_review,
        out_of_scope=out_of_scope,
        source="ia",
    )