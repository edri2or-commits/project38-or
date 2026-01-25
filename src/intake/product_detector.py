"""Product potential detector for personal needs.

Implements the "אם צורך אישי מתאים להפוך למוצר/אפליקציה — העלה למסלול מוצר מיוזמתך"
principle from the alignment prompt.

Detects when a personal need expressed by the user could potentially become:
- A SaaS product
- A mobile app
- A website/tool
- An AI agent
- A template/course

The detector looks for:
1. "I wish there was..." patterns
2. "I built for myself..." patterns
3. Problems that many people might have
4. Frustrations with existing solutions
5. Automation opportunities
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ProductPotential:
    """Result of product potential detection."""

    # Core assessment
    has_potential: bool = False
    score: float = 0.0  # 0.0 to 1.0
    confidence: float = 0.0

    # Product type suggestions
    suggested_types: list[str] = field(default_factory=list)
    # e.g., ["saas", "mobile_app", "ai_agent"]

    # Evidence
    signals: list[str] = field(default_factory=list)
    reasoning: str = ""

    # Market indicators
    problem_clarity: float = 0.0  # How clear is the problem?
    automation_potential: float = 0.0  # Can it be automated?
    market_size_indicator: str = "unknown"  # small, medium, large, unknown

    # Next steps
    suggested_validation_steps: list[str] = field(default_factory=list)

    # Metadata
    detected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class ProductDetector:
    """Detects when personal needs could become products.

    Uses pattern matching to identify product opportunities in user input.
    Designed to proactively surface opportunities without being pushy.

    Key patterns (Hebrew + English):
    - "I need something that..." / "אני צריך משהו ש..."
    - "Why isn't there..." / "למה אין..."
    - "I built for myself..." / "בניתי לעצמי..."
    - "Every time I have to..." / "כל פעם שאני צריך..."
    """

    # Wish patterns - "I wish there was..."
    WISH_PATTERNS = [
        # Hebrew - use non-capturing groups (?:) or no groups
        r"הלוואי.*היה",
        r"הלוואי שהיה",
        r"למה אין",
        r"חבל שאין",
        r"אני מחפש.*ש",
        r"צריך להיות",
        r"היה טוב אם",
        r"אם רק היה",
        # English
        r"i wish there was",
        r"i wish someone would",
        r"i wish i could",
        r"why isn't there",
        r"why is there no",
        r"if only there was",
        r"if only i had",
        r"looking for a tool that",
        r"looking for an app that",
        r"there should be",
    ]

    # Built-for-self patterns
    BUILT_PATTERNS = [
        # Hebrew
        r"בניתי לעצמי",
        r"יצרתי (כלי|סקריפט|אוטומציה)",
        r"כתבתי (קוד|סקריפט) ש",
        r"הכנתי (טבלה|מערכת|תהליך)",
        r"פיתחתי (משהו|כלי|פתרון)",
        # English
        r"i (built|made|created) (for myself|my own)",
        r"i wrote (a script|some code|an automation)",
        r"i put together (a spreadsheet|a system|a process)",
        r"i developed (something|a tool|a solution)",
    ]

    # Repetitive frustration patterns
    FRUSTRATION_PATTERNS = [
        # Hebrew - simplified without capture groups
        r"כל פעם.*אני.*צריך",
        r"כל פעם.*אני.*חייב",
        r"נמאס לי",
        r"מתסכל",
        r"בזבוז זמן",
        r"מבזבז זמן",
        r"תהליך מעצבן",
        r"תהליך מייגע",
        r"תהליך ארוך",
        # English
        r"every time i have to",
        r"every time i need to",
        r"i'm tired of",
        r"i am tired of",
        r"i'm sick of",
        r"i am sick of",
        r"it's frustrating",
        r"it is frustrating",
        r"waste time on",
        r"wasting time on",
        r"boring process",
        r"tedious task",
        r"repetitive task",
        r"repetitive work",
    ]

    # Automation opportunity patterns
    AUTOMATION_PATTERNS = [
        # Hebrew - simplified
        r"אפשר לאוטמ",
        r"צריך לאוטמ",
        r"חוזר על עצמ",
        r"חוזרת על עצמ",
        r"עושה את אותו דבר",
        r"עושה אותו תהליך",
        r"ידני מאוד",
        r"ידנית מאוד",
        r"ידני לגמרי",
        r"ידנית לגמרי",
        r"אם רק היה בוט",
        r"אם רק הייתה אוטומציה",
        # English
        r"could be automated",
        r"should be automated",
        r"needs to be automated",
        r"doing the same thing",
        r"do the same thing",
        r"manual process",
        r"manual work",
        r"manual task",
        r"manually",
        r"if only there was a bot",
        r"if only i had automation",
        r"repetitive task",
        r"recurring task",
        r"repetitive work",
    ]

    # Market size indicators
    LARGE_MARKET_INDICATORS = [
        r"everyone|כולם",
        r"all (businesses|companies|people)|כל (העסקים|האנשים)",
        r"(common|universal) problem|בעיה (נפוצה|אוניברסלית)",
        r"(millions|thousands) of|מיליוני|אלפי",
    ]

    MEDIUM_MARKET_INDICATORS = [
        r"many (people|businesses)|הרבה (אנשים|עסקים)",
        r"(my industry|our field)|התעשייה שלי",
        r"(freelancers|small businesses)|עצמאים|עסקים קטנים",
    ]

    # Product type indicators
    PRODUCT_TYPE_INDICATORS = {
        "saas": [r"(dashboard|platform|system)|דשבורד|פלטפורמה|מערכת"],
        "mobile_app": [r"(on my phone|mobile|app)|בטלפון|אפליקציה"],
        "ai_agent": [r"(ai|bot|assistant|automatically)|בינה|בוט|עוזר|אוטומטית"],
        "browser_extension": [r"(browser|chrome|extension)|דפדפן|תוסף"],
        "api_service": [r"(api|integration|connect)|אינטגרציה|חיבור"],
        "template": [r"(template|spreadsheet|document)|תבנית|טבלה|מסמך"],
        "course": [r"(learn|teach|course)|ללמוד|ללמד|קורס"],
    }

    # Threshold for flagging potential
    # 0.25 = single strong signal is enough
    POTENTIAL_THRESHOLD = 0.25

    def __init__(self):
        """Initialize detector with compiled patterns."""
        self._compiled = {
            "wish": [re.compile(p, re.IGNORECASE | re.UNICODE) for p in self.WISH_PATTERNS],
            "built": [re.compile(p, re.IGNORECASE | re.UNICODE) for p in self.BUILT_PATTERNS],
            "frustration": [re.compile(p, re.IGNORECASE | re.UNICODE) for p in self.FRUSTRATION_PATTERNS],
            "automation": [re.compile(p, re.IGNORECASE | re.UNICODE) for p in self.AUTOMATION_PATTERNS],
        }

    def detect(self, text: str, context: str = "") -> ProductPotential:
        """Detect product potential in user input.

        Args:
            text: The user's input text
            context: Optional additional context

        Returns:
            ProductPotential with assessment and suggestions
        """
        full_text = f"{text} {context}".strip().lower()

        # Collect signals from each pattern category
        signals: list[str] = []
        category_scores: dict[str, float] = {}

        for category, patterns in self._compiled.items():
            matches = []
            for pattern in patterns:
                found = pattern.findall(full_text)
                matches.extend(found)

            if matches:
                unique_matches = list(set(matches))[:3]
                signals.append(f"{category}: {', '.join(unique_matches)}")
                # Base score of 0.5 for any match, plus 0.15 per additional unique match
                category_scores[category] = min(0.5 + (len(set(matches)) - 1) * 0.15, 1.0)
            else:
                category_scores[category] = 0.0

        # Calculate overall score
        # Each category contributes independently - take max contribution
        # Single strong signal should be enough to flag potential
        weights = {"wish": 0.6, "built": 0.7, "frustration": 0.5, "automation": 0.5}

        # Use weighted max rather than sum to avoid dilution
        weighted_scores = [category_scores[k] * weights[k] for k in weights if category_scores[k] > 0]
        score = max(weighted_scores) if weighted_scores else 0.0

        # Boost if multiple categories match
        active_categories = sum(1 for v in category_scores.values() if v > 0)
        if active_categories >= 2:
            score = min(score + 0.15, 1.0)
        if active_categories >= 3:
            score = min(score + 0.15, 1.0)

        # Detect suggested product types
        suggested_types = self._detect_product_types(full_text)

        # Detect market size
        market_size = self._detect_market_size(full_text)

        # Calculate sub-scores
        problem_clarity = min(
            (category_scores.get("wish", 0) + category_scores.get("frustration", 0)) * 0.7,
            1.0
        )
        automation_potential = category_scores.get("automation", 0)

        # Determine if has potential
        has_potential = score >= self.POTENTIAL_THRESHOLD

        # Generate reasoning
        if has_potential:
            reasoning = self._generate_reasoning(category_scores, suggested_types, market_size)
            validation_steps = self._suggest_validation_steps(category_scores, suggested_types)
        else:
            reasoning = "No strong product indicators detected"
            validation_steps = []

        result = ProductPotential(
            has_potential=has_potential,
            score=round(score, 3),
            confidence=min(score + 0.1, 1.0) if active_categories >= 2 else score,
            suggested_types=suggested_types,
            signals=signals,
            reasoning=reasoning,
            problem_clarity=round(problem_clarity, 3),
            automation_potential=round(automation_potential, 3),
            market_size_indicator=market_size,
            suggested_validation_steps=validation_steps,
        )

        if has_potential:
            logger.info(
                f"ProductDetector: Potential found! score={score:.2f}, "
                f"types={suggested_types}, market={market_size}"
            )

        return result

    def _detect_product_types(self, text: str) -> list[str]:
        """Detect what type of product might fit the need."""
        types = []
        for product_type, patterns in self.PRODUCT_TYPE_INDICATORS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    types.append(product_type)
                    break

        # Default suggestions if none detected
        if not types:
            types = ["saas", "ai_agent"]  # Most common for automation needs

        return types

    def _detect_market_size(self, text: str) -> str:
        """Estimate potential market size from language."""
        for pattern in self.LARGE_MARKET_INDICATORS:
            if re.search(pattern, text, re.IGNORECASE):
                return "large"

        for pattern in self.MEDIUM_MARKET_INDICATORS:
            if re.search(pattern, text, re.IGNORECASE):
                return "medium"

        return "small"  # Default for personal needs

    def _generate_reasoning(
        self,
        scores: dict[str, float],
        types: list[str],
        market: str
    ) -> str:
        """Generate human-readable reasoning."""
        parts = []

        if scores.get("wish", 0) > 0:
            parts.append("User expressed a wish for a solution")
        if scores.get("built", 0) > 0:
            parts.append("User already built something (validation!)")
        if scores.get("frustration", 0) > 0:
            parts.append("User expressed frustration with current process")
        if scores.get("automation", 0) > 0:
            parts.append("Task has automation potential")

        if types:
            parts.append(f"Suggested formats: {', '.join(types)}")
        if market != "unknown":
            parts.append(f"Market size indicator: {market}")

        return ". ".join(parts) if parts else "Product potential detected"

    def _suggest_validation_steps(
        self,
        scores: dict[str, float],
        types: list[str]
    ) -> list[str]:
        """Suggest next steps for validation."""
        steps = []

        # Always start with problem validation
        steps.append("Validate the problem: Is this a real pain point for others?")

        if scores.get("built", 0) > 0:
            steps.append("Document your existing solution - it's a prototype!")
            steps.append("Consider if others would pay for a polished version")

        if "ai_agent" in types:
            steps.append("Test if AI can reliably solve this problem")
            steps.append("Estimate API costs for the solution")

        if "saas" in types:
            steps.append("Create a simple landing page to test interest")
            steps.append("Define the minimum viable feature set")

        steps.append("Research competitors - what exists? What's missing?")

        return steps[:5]  # Limit to 5 actionable steps


def should_flag_for_product_track(
    text: str,
    domain_result: Any = None,  # DomainClassification
    threshold: float = 0.5
) -> tuple[bool, ProductPotential]:
    """Convenience function to check if input should go to product track.

    This implements the alignment prompt requirement:
    "אם צורך אישי מתאים להפוך למוצר/אפליקציה — העלה למסלול מוצר מיוזמתך"

    Args:
        text: User input text
        domain_result: Optional domain classification result
        threshold: Score threshold for flagging

    Returns:
        Tuple of (should_flag, potential_details)
    """
    detector = ProductDetector()
    potential = detector.detect(text)

    # Extra weight if it's a personal domain with product potential
    if domain_result and hasattr(domain_result, "domain"):
        if domain_result.domain.value == "personal" and potential.score > 0.3:
            potential.score = min(potential.score + 0.1, 1.0)
            potential.reasoning += " [Boosted: Personal need with product potential]"

    should_flag = potential.score >= threshold
    return should_flag, potential
