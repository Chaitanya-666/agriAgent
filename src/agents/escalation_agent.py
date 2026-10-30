"""
src/agents/escalation_agent.py
The one agent in AgriAgent (task T1.7): reviews plants the safety gate withheld.

For each withheld plant the agent gathers evidence from cheap to expensive sources (row rule,
then Clef Flash, then the Groq vision model) and stops as soon as the evidence is decisive or
its call budget is spent. It returns a verdict per plant with a trace of every call, so each
decision can be explained. It only advises: the deterministic gate in src/workflow.py decides
whether a plant the agent calls "weed" is sprayed.

Combining evidence (naive Bayes, starting from even odds): a source's stated confidence is
not its accuracy, so each answer is first capped by the source's measured accuracy on labelled
patches (T2.2, 20 patches: Groq 16/20, Clef Flash 14/20, row rule 13/20):

    P(answer is right) = accuracy * confidence + (1 - accuracy) * (1 - confidence)

The answers' likelihood ratios are then multiplied, assuming the sources err independently.
One source alone can therefore never reach the decision level (0.85); two independent
sources that agree can, and sources that disagree cancel out to "unsure".
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from PIL import Image

from src.agents.evidence import ClefEvidence, Evidence, QwenVlmEvidence, RowRuleEvidence

# Measured accuracy of each source on the 20 labelled patches of T2.2. qwen_vlm was measured as
# "groq_vlm": the same Qwen model, then served by Groq.
DEFAULT_WEIGHTS = {"row_rule": 0.65, "clef_flash": 0.70, "qwen_vlm": 0.80}


@dataclass
class Review:
    """The agent's verdict on one withheld plant."""

    index: int  # position of the mask in the workflow state
    label: str
    verdict: str  # "weed", "crop" or "unsure"
    p_weed: Optional[float]
    calls_used: int
    trace: List[Evidence] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "label": self.label,
            "verdict": self.verdict,
            "p_weed": None if self.p_weed is None else round(self.p_weed, 3),
            "calls_used": self.calls_used,
            "trace": [
                {
                    "source": e.source,
                    "verdict": e.verdict,
                    "confidence": round(e.confidence, 3),
                    "detail": e.detail,
                }
                for e in self.trace
            ],
        }


class EscalationAgent:
    def __init__(
        self,
        sources: Optional[Sequence[Any]] = None,
        weights: Optional[Dict[str, float]] = None,
        decide_at: float = 0.85,
        budget_per_image: int = 12,
        max_plants: int = 6,
    ):
        """
        sources: evidence sources tried in this order (cheapest first).
        decide_at: stop when P(weed) >= decide_at (weed) or <= 1 - decide_at (crop).
        budget_per_image: total call cost allowed per photo (row rule 0, Clef 1, Groq 3).
        max_plants: plants reviewed per photo, largest first; the rest stay withheld.
        """
        self.sources: List[Any] = (
            list(sources)
            if sources is not None
            else [RowRuleEvidence(), ClefEvidence(), QwenVlmEvidence()]
        )
        self.weights = weights or DEFAULT_WEIGHTS
        self.decide_at = decide_at
        self.budget_per_image = budget_per_image
        self.max_plants = max_plants

    def p_weed(self, trace: List[Evidence]) -> Optional[float]:
        """Probability that the plant is a weed, combining the answers so far (see module doc)."""
        odds, answers = 1.0, 0
        for e in trace:
            if e.verdict is None:
                continue
            accuracy = self.weights.get(e.source, 0.5)
            right = accuracy * e.confidence + (1 - accuracy) * (1 - e.confidence)
            p = right if e.verdict == "weed" else 1 - right
            p = min(0.98, max(0.02, p))
            odds *= p / (1 - p)
            answers += 1
        return None if answers == 0 else odds / (1 + odds)

    def review_plant(self, image: Image.Image, box: List[float], crop: str, budget: int) -> Review:
        trace: List[Evidence] = []
        used = 0
        for source in self.sources:
            if used + source.cost > budget:
                continue
            evidence = source(image, box, crop)
            trace.append(evidence)
            used += evidence.cost
            p = self.p_weed(trace)
            if p is not None and (p >= self.decide_at or p <= 1 - self.decide_at):
                break
        p = self.p_weed(trace)
        if p is None:
            verdict = "unsure"
        elif p >= self.decide_at:
            verdict = "weed"
        elif p <= 1 - self.decide_at:
            verdict = "crop"
        else:
            verdict = "unsure"
        return Review(-1, "", verdict, p, used, trace)

    def review(
        self, image: Image.Image, candidates: List[Dict[str, Any]], crop: str
    ) -> List[Review]:
        """
        candidates: dicts with "index", "label" and "box" ([x1, y1, x2, y2]) for withheld plants.
        Larger plants first, since they matter most for the spray map.
        """
        ordered = sorted(
            candidates,
            key=lambda c: (c["box"][2] - c["box"][0]) * (c["box"][3] - c["box"][1]),
            reverse=True,
        )
        remaining = self.budget_per_image
        reviews = []
        for candidate in ordered[: self.max_plants]:
            review = self.review_plant(image, candidate["box"], crop, remaining)
            review.index, review.label = candidate["index"], candidate["label"]
            remaining -= review.calls_used
            reviews.append(review)
        return reviews
