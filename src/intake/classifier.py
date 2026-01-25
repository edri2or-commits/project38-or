"""Intake Classifier - Unified classification for the intake system.

Combines domain classification, product detection, and task classification
into a single classification pipeline with confidence-based cascade.

Architecture (from External Research 2026 §3.2):
1. Rule-based classification first (fast, free)
2. If confidence < threshold → escalate to Haiku 4.5
3. If still uncertain → escalate to Sonnet 4.5
4. Inter-Cascade: Sonnet responses teach Haiku over time

Integrates:
- DomainClassifier: personal/business/mixed
- ProductDetector: product potential identification
- TaskClassifier: task type for model selection (from smart_llm)
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.intake.domain_classifier import DomainClassifier, DomainClassification, Domain
from src.intake.product_detector import ProductDetector, ProductPotential
from src.intake.queue import IntakeEvent, EventType

# Import TaskClassifier if available
try:
    from src.smart_llm.classifier import TaskClassifier, ClassificationResult as TaskResult
except ImportError:
    TaskClassifier = None  # type: ignore
    TaskResult = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class IntakeClassificationResult:
    """Complete classification result for an intake event."""

    # Domain classification
    domain: Domain
    domain_confidence: float
    domain_category: str | None = None  # health, client, etc.

    # Product potential
    has_product_potential: bool = False
    product_score: float = 0.0
    product_types: list[str] = field(default_factory=list)

    # Task classification (from smart_llm)
    task_type: str | None = None
    suggested_model: str = "claude-haiku"
    task_confidence: float = 0.0

    # Priority (P1-P4)
    priority: str = "P3"

    # Routing decision
    route_to: str | None = None  # skill name or agent
    action_required: bool = False

    # Classification metadata
    classified_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    classification_method: str = "rule_based"  # rule_based, haiku, sonnet
    escalated: bool = False
    escalation_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "domain": self.domain.value,
            "domain_confidence": self.domain_confidence,
            "domain_category": self.domain_category,
            "has_product_potential": self.has_product_potential,
            "product_score": self.product_score,
            "product_types": self.product_types,
            "task_type": self.task_type,
            "suggested_model": self.suggested_model,
            "task_confidence": self.task_confidence,
            "priority": self.priority,
            "route_to": self.route_to,
            "action_required": self.action_required,
            "classified_at": self.classified_at,
            "classification_method": self.classification_method,
            "escalated": self.escalated,
            "escalation_reason": self.escalation_reason,
        }


@dataclass
class FewShotExample:
    """Example for Inter-Cascade learning."""

    query: str
    domain: str
    classification: dict[str, Any]
    model_used: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class FewShotStore:
    """Stores high-quality examples for Inter-Cascade learning.

    When Sonnet produces a high-confidence classification,
    it's stored here so Haiku can learn from it.

    External Research 2026 §3.2.2:
    "The strong model effectively 'teaches' the weak model.
    Over time, Haiku's performance on that specific domain improves."
    """

    def __init__(self, store_path: Path | None = None, max_examples: int = 100):
        """Initialize the few-shot store.

        Args:
            store_path: Path to persist examples. If None, uses in-memory only.
            max_examples: Maximum examples to keep per domain.
        """
        self._store_path = store_path
        self._max_examples = max_examples
        self._examples: dict[str, list[FewShotExample]] = {
            "personal": [],
            "business": [],
            "mixed": [],
        }
        self._load()

    def _load(self) -> None:
        """Load examples from disk if available."""
        if self._store_path and self._store_path.exists():
            try:
                data = json.loads(self._store_path.read_text())
                for domain, examples in data.items():
                    self._examples[domain] = [
                        FewShotExample(**ex) for ex in examples
                    ]
                logger.info(f"FewShotStore: Loaded {sum(len(v) for v in self._examples.values())} examples")
            except Exception as e:
                logger.warning(f"FewShotStore: Failed to load: {e}")

    def _save(self) -> None:
        """Persist examples to disk."""
        if self._store_path:
            try:
                data = {
                    domain: [
                        {
                            "query": ex.query,
                            "domain": ex.domain,
                            "classification": ex.classification,
                            "model_used": ex.model_used,
                            "created_at": ex.created_at,
                        }
                        for ex in examples
                    ]
                    for domain, examples in self._examples.items()
                }
                self._store_path.write_text(json.dumps(data, indent=2))
            except Exception as e:
                logger.warning(f"FewShotStore: Failed to save: {e}")

    def add(
        self,
        query: str,
        domain: str,
        classification: dict[str, Any],
        model_used: str
    ) -> None:
        """Add a high-quality example from Sonnet.

        Args:
            query: Original user query
            domain: Classified domain
            classification: Full classification result
            model_used: Model that produced this (should be sonnet)
        """
        if domain not in self._examples:
            domain = "mixed"

        example = FewShotExample(
            query=query[:500],  # Truncate for storage
            domain=domain,
            classification=classification,
            model_used=model_used
        )

        self._examples[domain].append(example)

        # Trim old examples
        if len(self._examples[domain]) > self._max_examples:
            self._examples[domain] = self._examples[domain][-self._max_examples:]

        self._save()
        logger.debug(f"FewShotStore: Added example for domain={domain}")

    def get_examples(self, domain: str, count: int = 3) -> list[FewShotExample]:
        """Get recent examples for a domain.

        Args:
            domain: Domain to get examples for
            count: Number of examples to return

        Returns:
            Most recent examples for the domain
        """
        if domain not in self._examples:
            return []
        return self._examples[domain][-count:]

    def format_for_prompt(self, domain: str, count: int = 2) -> str:
        """Format examples for inclusion in a prompt.

        Args:
            domain: Domain to get examples for
            count: Number of examples

        Returns:
            Formatted string for prompt injection
        """
        examples = self.get_examples(domain, count)
        if not examples:
            return ""

        parts = ["Here are some example classifications:"]
        for i, ex in enumerate(examples, 1):
            parts.append(f"\nExample {i}:")
            parts.append(f"Query: {ex.query[:200]}")
            parts.append(f"Classification: {json.dumps(ex.classification, ensure_ascii=False)}")

        return "\n".join(parts)


class IntakeClassifier:
    """Unified classifier for the intake system.

    Combines multiple classifiers with confidence-based cascade:
    1. Rule-based (DomainClassifier, ProductDetector, TaskClassifier)
    2. Haiku 4.5 for uncertain cases
    3. Sonnet 4.5 for complex cases

    The Inter-Cascade pattern means Sonnet responses improve Haiku over time.
    """

    # Confidence thresholds
    RULE_BASED_THRESHOLD = 0.7  # Above this, trust rule-based
    HAIKU_THRESHOLD = 0.6  # Below this, escalate to Sonnet
    ESCALATION_THRESHOLD = 0.5  # Below this, definitely escalate

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        few_shot_store: FewShotStore | None = None,
        enable_cascade: bool = True
    ):
        """Initialize the classifier.

        Args:
            llm_client: SmartLLMClient for LLM-assisted classification.
                       If None, uses rule-based only.
            few_shot_store: Store for Inter-Cascade learning.
            enable_cascade: Whether to enable cascade to stronger models.
        """
        self._llm = llm_client
        self._few_shot_store = few_shot_store or FewShotStore()
        self._enable_cascade = enable_cascade

        # Initialize sub-classifiers
        self._domain_classifier = DomainClassifier(llm_client=None)  # Rule-based first
        self._product_detector = ProductDetector()
        self._task_classifier = TaskClassifier() if TaskClassifier else None

    def classify(self, text: str, context: str = "") -> IntakeClassificationResult:
        """Classify user input with confidence-based cascade.

        Args:
            text: User input text
            context: Additional context

        Returns:
            Complete classification result
        """
        full_text = f"{text} {context}".strip()

        # Step 1: Rule-based classification
        domain_result = self._domain_classifier.classify(text, context)
        product_result = self._product_detector.detect(text, context)

        # Task classification if available
        task_result = None
        if self._task_classifier:
            task_result = self._task_classifier.classify(text, context)

        # Calculate combined confidence
        combined_confidence = domain_result.confidence
        if task_result:
            combined_confidence = (domain_result.confidence + task_result.confidence) / 2

        # Determine if we need to escalate
        method = "rule_based"
        escalated = False
        escalation_reason = None

        if combined_confidence < self.RULE_BASED_THRESHOLD and self._enable_cascade:
            # Try Haiku first
            if self._llm and combined_confidence < self.ESCALATION_THRESHOLD:
                haiku_result = self._classify_with_haiku(full_text, domain_result)
                if haiku_result:
                    domain_result = haiku_result["domain_result"]
                    combined_confidence = haiku_result["confidence"]
                    method = "haiku"
                    escalated = True
                    escalation_reason = "Rule-based confidence too low"

                    # If Haiku still uncertain, try Sonnet
                    if combined_confidence < self.HAIKU_THRESHOLD:
                        sonnet_result = self._classify_with_sonnet(full_text, domain_result)
                        if sonnet_result:
                            domain_result = sonnet_result["domain_result"]
                            combined_confidence = sonnet_result["confidence"]
                            method = "sonnet"
                            escalation_reason = "Haiku confidence too low"

                            # Inter-Cascade: Store Sonnet's result to teach Haiku
                            self._few_shot_store.add(
                                query=text,
                                domain=domain_result.domain.value,
                                classification=domain_result.__dict__ if hasattr(domain_result, '__dict__') else {},
                                model_used="sonnet"
                            )

        # Determine priority
        priority = self._calculate_priority(domain_result, product_result)

        # Determine routing
        route_to = self._determine_routing(domain_result, product_result, task_result)

        return IntakeClassificationResult(
            domain=domain_result.domain,
            domain_confidence=domain_result.confidence,
            domain_category=domain_result.personal_category or domain_result.business_category,
            has_product_potential=product_result.has_potential,
            product_score=product_result.score,
            product_types=product_result.suggested_types,
            task_type=task_result.task_type.value if task_result else None,
            suggested_model=task_result.suggested_model if task_result else "claude-haiku",
            task_confidence=task_result.confidence if task_result else 0.0,
            priority=priority,
            route_to=route_to,
            action_required=product_result.has_potential or priority in ("P1", "P2"),
            classification_method=method,
            escalated=escalated,
            escalation_reason=escalation_reason,
        )

    def _classify_with_haiku(
        self,
        text: str,
        rule_result: DomainClassification
    ) -> dict[str, Any] | None:
        """Classify with Haiku 4.5 using few-shot examples.

        Args:
            text: Input text
            rule_result: Rule-based classification result

        Returns:
            Classification result or None if failed
        """
        if not self._llm:
            return None

        # Get few-shot examples for this domain
        examples = self._few_shot_store.format_for_prompt(
            rule_result.domain.value,
            count=2
        )

        prompt = f"""Classify this user input into one of three domains:
- PERSONAL: health, family, hobbies, self-improvement, home life
- BUSINESS: projects, clients, products, revenue, marketing, work
- MIXED: freelance, side projects, work-from-home that blends both

{examples}

User input: {text[:500]}

Respond with JSON only:
{{"domain": "personal|business|mixed", "confidence": 0.0-1.0, "category": "specific subcategory", "reasoning": "brief explanation"}}"""

        try:
            response = self._llm.complete(
                model="claude-haiku",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200
            )

            result = json.loads(response.content)
            return {
                "domain_result": DomainClassification(
                    domain=Domain(result["domain"]),
                    confidence=float(result["confidence"]),
                    reasoning=result.get("reasoning", ""),
                    personal_category=result.get("category") if result["domain"] == "personal" else None,
                    business_category=result.get("category") if result["domain"] == "business" else None,
                    method="llm"
                ),
                "confidence": float(result["confidence"])
            }
        except Exception as e:
            logger.warning(f"Haiku classification failed: {e}")
            return None

    def _classify_with_sonnet(
        self,
        text: str,
        current_result: DomainClassification
    ) -> dict[str, Any] | None:
        """Classify with Sonnet 4.5 for complex cases.

        Args:
            text: Input text
            current_result: Current classification result

        Returns:
            Classification result or None if failed
        """
        if not self._llm:
            return None

        prompt = f"""You are a classification expert. Carefully analyze this input and classify it.

Current uncertain classification:
- Domain: {current_result.domain.value}
- Confidence: {current_result.confidence}
- Reasoning: {current_result.reasoning}

User input: {text[:800]}

Provide a definitive classification. Consider:
1. Primary life domain (personal vs business vs mixed)
2. Specific category (health, client, product, etc.)
3. Whether this could become a product/service
4. Required action or just informational

Respond with JSON only:
{{
  "domain": "personal|business|mixed",
  "confidence": 0.0-1.0,
  "category": "specific subcategory",
  "reasoning": "detailed explanation",
  "product_potential": true|false,
  "action_required": true|false
}}"""

        try:
            response = self._llm.complete(
                model="claude-sonnet",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300
            )

            result = json.loads(response.content)
            return {
                "domain_result": DomainClassification(
                    domain=Domain(result["domain"]),
                    confidence=float(result["confidence"]),
                    reasoning=result.get("reasoning", ""),
                    personal_category=result.get("category") if result["domain"] == "personal" else None,
                    business_category=result.get("category") if result["domain"] == "business" else None,
                    method="llm"
                ),
                "confidence": float(result["confidence"]),
                "product_potential": result.get("product_potential", False),
                "action_required": result.get("action_required", False)
            }
        except Exception as e:
            logger.warning(f"Sonnet classification failed: {e}")
            return None

    def _calculate_priority(
        self,
        domain: DomainClassification,
        product: ProductPotential
    ) -> str:
        """Calculate priority level (P1-P4).

        P1: Urgent - deadlines, critical business
        P2: Important - action required
        P3: Normal - standard processing
        P4: Low - informational, promotional
        """
        # Product potential with business domain = high priority
        if product.has_potential and domain.domain == Domain.BUSINESS:
            return "P1"

        # Product potential with personal = moderate priority
        if product.has_potential:
            return "P2"

        # Business domain = moderate priority
        if domain.domain == Domain.BUSINESS:
            return "P2"

        # Mixed = normal
        if domain.domain == Domain.MIXED:
            return "P3"

        # Personal = lower priority (unless health-related)
        if domain.personal_category == "health":
            return "P2"

        return "P3"

    def _determine_routing(
        self,
        domain: DomainClassification,
        product: ProductPotential,
        task: Any | None
    ) -> str | None:
        """Determine which skill/agent should handle this input."""
        # Product potential → adr-architect skill
        if product.has_potential:
            return "adr-architect"

        # Business queries → relevant business skills
        if domain.domain == Domain.BUSINESS:
            if domain.business_category == "client":
                return "email-assistant"
            if domain.business_category == "product":
                return "adr-architect"
            return "general"

        # Research tasks
        if task and hasattr(task, 'task_type'):
            if task.task_type.value == "research":
                return "research-ingestion"

        return "general"

    def classify_event(self, event: IntakeEvent) -> IntakeEvent:
        """Classify an intake event and update its fields.

        Args:
            event: IntakeEvent to classify

        Returns:
            Updated event with classification fields
        """
        result = self.classify(event.content)

        # Update event fields
        event.domain = result.domain.value
        event.priority = result.priority
        event.product_potential = result.product_score
        event.product_signals = result.product_types
        event.routed_to = result.route_to
        event.metadata["classification"] = result.to_dict()

        return event
