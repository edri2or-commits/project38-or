"""Domain classifier for personal/business/mixed categorization.

Implements the "מיון עצמי + מודעות מצב" principle from alignment prompt:
- Automatically identify which domain each input belongs to
- Support personal, business, and mixed domains
- Enable routing to appropriate processing pipelines

Classification uses Haiku 4.5 for cost efficiency (validated by External Research 2026 §3.1).
Falls back to rule-based classification when LLM unavailable.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class Domain(str, Enum):
    """Life domains for input classification."""

    PERSONAL = "personal"  # Health, family, hobbies, self-improvement
    BUSINESS = "business"  # Projects, clients, products, revenue
    MIXED = "mixed"  # Freelance, work-from-home, side projects


@dataclass
class DomainClassification:
    """Result of domain classification."""

    domain: Domain
    confidence: float  # 0.0 to 1.0
    reasoning: str = ""

    # Sub-categories
    personal_category: str | None = None  # health, family, hobby, etc.
    business_category: str | None = None  # client, product, marketing, etc.

    # Signals that led to classification
    signals: list[str] = field(default_factory=list)

    # Metadata
    classified_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    classifier_version: str = "1.0.0"
    method: str = "rule_based"  # rule_based or llm


class DomainClassifier:
    """Classifies input into personal/business/mixed domains.

    Uses a hybrid approach:
    1. Rule-based for high-confidence patterns (fast, free)
    2. Haiku 4.5 LLM for ambiguous cases (accurate, low cost)

    The classifier supports Hebrew and English keywords.
    """

    # Hebrew and English patterns for each domain
    PERSONAL_PATTERNS = [
        # Hebrew
        r"אישי|משפחה|בריאות|כושר|דיאטה|רופא|תור",
        r"חופש|חופשה|טיול|תחביב|ספורט|יוגה",
        r"ילדים|הורים|בן זוג|חברים|משפחתי",
        r"שינה|מנוחה|סטרס|חרדה|רגשות",
        r"בית|דירה|שיפוץ|ריהוט|גינה",
        r"קניות אישיות|מתנה|יום הולדת",
        # English
        r"personal|family|health|fitness|doctor|appointment",
        r"vacation|travel|hobby|sport|yoga|meditation",
        r"kids|parents|spouse|friends|relationship",
        r"sleep|rest|stress|anxiety|mental",
        r"home|apartment|renovation|furniture|garden",
    ]

    BUSINESS_PATTERNS = [
        # Hebrew
        r"עסק|פרויקט|לקוח|מוצר|הכנסה|רווח",
        r"שיווק|מכירות|פרסום|קמפיין",
        r"חשבונית|תשלום עסקי|ספק|קבלן",
        r"עובד|צוות|גיוס|משרה|שכר",
        r"חברה|סטארטאפ|מיזם|השקעה",
        r"אתר|אפליקציה|פיתוח|קוד|טכנולוגיה",
        r"פגישה עסקית|הצעת מחיר|חוזה",
        # English
        r"business|project|client|product|revenue|profit",
        r"marketing|sales|advertising|campaign",
        r"invoice|payment|supplier|contractor",
        r"employee|team|hiring|position|salary",
        r"company|startup|venture|investment",
        r"website|app|development|code|technology",
        r"meeting|proposal|contract|deal",
    ]

    MIXED_PATTERNS = [
        # Hebrew
        r"פרילנס|עצמאי|עבודה מהבית",
        r"פרויקט צד|הכנסה פסיבית",
        r"קורס|לימודים|הכשרה",  # Can be both
        r"רשת חברתית|לינקדאין|פייסבוק",  # Can be both
        # English
        r"freelance|self.?employed|work.?from.?home|remote",
        r"side.?project|passive.?income|hustle",
        r"course|learning|training",
        r"social.?media|linkedin|networking",
    ]

    # Confidence thresholds
    HIGH_CONFIDENCE_THRESHOLD = 0.8
    LLM_ESCALATION_THRESHOLD = 0.6

    def __init__(self, llm_client=None):
        """Initialize classifier.

        Args:
            llm_client: Optional LLM client for ambiguous cases.
                       Should support Haiku 4.5 for cost efficiency.
        """
        self._llm = llm_client
        self._compiled_patterns = self._compile_patterns()

    def _compile_patterns(self) -> dict[Domain, list[re.Pattern]]:
        """Pre-compile regex patterns for performance."""
        return {
            Domain.PERSONAL: [re.compile(p, re.IGNORECASE | re.UNICODE)
                             for p in self.PERSONAL_PATTERNS],
            Domain.BUSINESS: [re.compile(p, re.IGNORECASE | re.UNICODE)
                             for p in self.BUSINESS_PATTERNS],
            Domain.MIXED: [re.compile(p, re.IGNORECASE | re.UNICODE)
                          for p in self.MIXED_PATTERNS],
        }

    def classify(self, text: str, context: str = "") -> DomainClassification:
        """Classify text into a domain.

        Args:
            text: The input text to classify
            context: Optional additional context

        Returns:
            DomainClassification with domain and confidence
        """
        full_text = f"{text} {context}".strip()

        # Step 1: Rule-based classification
        result = self._rule_based_classify(full_text)

        # Step 2: If low confidence and LLM available, escalate
        if (result.confidence < self.LLM_ESCALATION_THRESHOLD
                and self._llm is not None):
            llm_result = self._llm_classify(full_text)
            if llm_result.confidence > result.confidence:
                result = llm_result

        logger.info(
            f"DomainClassifier: {result.domain.value} "
            f"(confidence={result.confidence:.2f}, method={result.method})"
        )
        return result

    def _rule_based_classify(self, text: str) -> DomainClassification:
        """Rule-based classification using patterns."""
        scores: dict[Domain, tuple[float, list[str]]] = {
            Domain.PERSONAL: (0.0, []),
            Domain.BUSINESS: (0.0, []),
            Domain.MIXED: (0.0, []),
        }

        # Count matches for each domain
        for domain, patterns in self._compiled_patterns.items():
            signals = []
            for pattern in patterns:
                matches = pattern.findall(text)
                if matches:
                    signals.extend(matches)

            if signals:
                # Score based on number of unique matches
                score = min(len(set(signals)) * 0.2, 1.0)
                scores[domain] = (score, list(set(signals)))

        # Determine winning domain
        personal_score, personal_signals = scores[Domain.PERSONAL]
        business_score, business_signals = scores[Domain.BUSINESS]
        mixed_score, mixed_signals = scores[Domain.MIXED]

        # Mixed wins if both personal and business have signals
        if personal_signals and business_signals:
            return DomainClassification(
                domain=Domain.MIXED,
                confidence=min((personal_score + business_score) / 2 + 0.2, 0.95),
                reasoning="Contains both personal and business indicators",
                signals=personal_signals + business_signals,
                method="rule_based"
            )

        # Otherwise, highest score wins
        if mixed_score > 0 and mixed_score >= max(personal_score, business_score):
            return DomainClassification(
                domain=Domain.MIXED,
                confidence=mixed_score,
                reasoning="Matches mixed/hybrid patterns",
                signals=mixed_signals,
                method="rule_based"
            )

        if personal_score >= business_score:
            domain = Domain.PERSONAL
            confidence = personal_score
            signals = personal_signals
            category = self._detect_personal_category(text)
        else:
            domain = Domain.BUSINESS
            confidence = business_score
            signals = business_signals
            category = self._detect_business_category(text)

        # Default to personal with low confidence if no signals
        if confidence == 0:
            domain = Domain.PERSONAL
            confidence = 0.3
            signals = []

        return DomainClassification(
            domain=domain,
            confidence=confidence,
            reasoning=f"Matched {len(signals)} patterns for {domain.value}",
            signals=signals,
            personal_category=category if domain == Domain.PERSONAL else None,
            business_category=category if domain == Domain.BUSINESS else None,
            method="rule_based"
        )

    def _detect_personal_category(self, text: str) -> str | None:
        """Detect specific personal category."""
        categories = {
            "health": r"בריאות|רופא|תור|כושר|דיאטה|health|doctor|fitness",
            "family": r"משפחה|ילדים|הורים|בן זוג|family|kids|parents",
            "hobby": r"תחביב|ספורט|יוגה|hobby|sport|yoga",
            "home": r"בית|דירה|שיפוץ|home|apartment|renovation",
            "travel": r"טיול|חופשה|travel|vacation",
            "wellbeing": r"שינה|סטרס|מנוחה|sleep|stress|rest",
        }

        for category, pattern in categories.items():
            if re.search(pattern, text, re.IGNORECASE):
                return category
        return None

    def _detect_business_category(self, text: str) -> str | None:
        """Detect specific business category."""
        categories = {
            "client": r"לקוח|client|customer",
            "product": r"מוצר|אפליקציה|אתר|product|app|website",
            "marketing": r"שיווק|פרסום|marketing|advertising",
            "finance": r"חשבונית|תשלום|הכנסה|invoice|payment|revenue",
            "team": r"צוות|עובד|גיוס|team|employee|hiring",
            "project": r"פרויקט|project",
        }

        for category, pattern in categories.items():
            if re.search(pattern, text, re.IGNORECASE):
                return category
        return None

    def _llm_classify(self, text: str) -> DomainClassification:
        """Use LLM for classification (Haiku 4.5 recommended).

        This is called only when rule-based confidence is low.
        """
        if self._llm is None:
            return DomainClassification(
                domain=Domain.PERSONAL,
                confidence=0.3,
                reasoning="LLM not available, defaulting to personal",
                method="fallback"
            )

        prompt = f"""Classify this input into one of three domains:
- PERSONAL: health, family, hobbies, self-improvement, home
- BUSINESS: projects, clients, products, revenue, marketing
- MIXED: freelance, side projects, work that blends personal/business

Input: {text[:500]}

Respond with JSON:
{{"domain": "personal|business|mixed", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}"""

        try:
            # Async would be better, but keeping sync for simplicity
            import json
            response = self._llm.complete(
                model="claude-haiku",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150
            )

            result = json.loads(response.content)
            return DomainClassification(
                domain=Domain(result["domain"]),
                confidence=float(result["confidence"]),
                reasoning=result.get("reasoning", ""),
                method="llm"
            )
        except Exception as e:
            logger.warning(f"LLM classification failed: {e}")
            return DomainClassification(
                domain=Domain.PERSONAL,
                confidence=0.3,
                reasoning=f"LLM error: {e}",
                method="llm_fallback"
            )

    def classify_batch(self, texts: list[str]) -> list[DomainClassification]:
        """Classify multiple texts efficiently."""
        return [self.classify(text) for text in texts]
