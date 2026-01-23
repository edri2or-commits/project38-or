"""
Task Classifier for automatic model selection.

Analyzes prompts to determine the optimal task type and model.
Uses pattern matching and heuristics for fast, cost-free classification.

ADR-013: Smart Model Routing Implementation
"""

import re
from dataclasses import dataclass
from enum import Enum


class TaskType(str, Enum):
    """Task types for automatic model selection.

    Each task type maps to an optimal model tier based on cost/quality tradeoff.
    """

    # TIER 1: Ultra-Cheap (< $1/1M output)
    SIMPLE = "simple"  # Q&A, basic questions → gemini-flash
    TRANSLATE = "translate"  # Translation → gemini-flash
    SUMMARIZE = "summarize"  # Summarization → gemini-flash
    FORMAT = "format"  # Formatting, conversion → gemini-flash

    # TIER 1-2: Budget coding
    CODING = "coding"  # Code generation → deepseek-v3
    MATH = "math"  # Math problems → deepseek-v3
    DATA = "data"  # Data processing → gpt-4o-mini

    # TIER 2: Budget analysis
    ANALYSIS = "analysis"  # Analysis → claude-haiku
    REVIEW = "review"  # Code review → claude-haiku
    DEBUG = "debug"  # Debugging → claude-haiku

    # TIER 3: Premium
    FEATURE = "feature"  # Feature development → claude-sonnet
    REFACTOR = "refactor"  # Refactoring → claude-sonnet
    COMPLEX = "complex"  # Complex tasks → claude-sonnet

    # TIER 4: Premium+
    ARCHITECTURE = "architecture"  # System design → claude-opus
    RESEARCH = "research"  # Deep research → deepseek-r1
    CRITICAL = "critical"  # Critical decisions → claude-opus

    # Default
    GENERAL = "general"  # General tasks → claude-haiku


class Tier(str, Enum):
    """Cost tiers for model selection."""

    ULTRA_CHEAP = "tier1"  # < $1/1M output
    BUDGET = "tier2"  # $1-5/1M output
    PREMIUM = "tier3"  # $5-15/1M output
    PREMIUM_PLUS = "tier4"  # $15+/1M output


@dataclass
class ClassificationResult:
    """Result of task classification."""

    task_type: TaskType
    tier: Tier
    confidence: float  # 0-1
    reason: str
    suggested_model: str


# Pattern definitions for each task type
TASK_PATTERNS: dict[TaskType, list[str]] = {
    # TIER 1: Ultra-Cheap
    TaskType.SIMPLE: [
        r"\b(what is|what are|who is|when did|where is|explain|define)\b",
        r"\b(tell me about|describe|list)\b",
        r"^\s*(hi|hello|hey|thanks|thank you)\s*$",
    ],
    TaskType.TRANSLATE: [
        r"\b(translate|translation|לתרגם|תרגם)\b",
        r"\b(to (english|hebrew|spanish|french|german))\b",
    ],
    TaskType.SUMMARIZE: [
        r"\b(summarize|summary|סכם|סיכום|תמצת)\b",
        r"\b(tldr|tl;dr|brief|briefly)\b",
    ],
    TaskType.FORMAT: [
        r"\b(format|reformat|convert to|change to)\b",
        r"\b(json|yaml|xml|csv|markdown)\b.*\b(format|convert)\b",
    ],
    # TIER 1-2: Budget coding
    TaskType.CODING: [
        r"\b(write|create|implement|code|function|class|method)\b.*\b(code|function|script)\b",
        r"\b(python|javascript|typescript|java|rust|go|c\+\+)\b.*\b(code|function)\b",
        r"```",  # Code blocks in prompt
        r"\b(algorithm|data structure|leetcode|hackerrank)\b",
    ],
    TaskType.MATH: [
        r"\b(calculate|compute|solve|equation|formula)\b",
        r"\b(math|mathematics|calculus|algebra|statistics)\b",
        r"[0-9]+\s*[\+\-\*\/\^]\s*[0-9]+",  # Mathematical expressions
    ],
    TaskType.DATA: [
        r"\b(parse|extract|process|transform)\b.*\b(data|json|csv)\b",
        r"\b(database|sql|query)\b",
    ],
    # TIER 2: Budget analysis
    TaskType.ANALYSIS: [
        r"\b(analyze|analysis|evaluate|assess|review)\b",
        r"\b(compare|comparison|difference|pros and cons)\b",
    ],
    TaskType.REVIEW: [
        r"\b(review|critique|feedback|improve)\b.*\b(code|pr|pull request)\b",
        r"\b(code review|peer review)\b",
    ],
    TaskType.DEBUG: [
        r"\b(debug|fix|error|bug|issue|problem)\b",
        r"\b(traceback|exception|stack trace)\b",
        r"\b(why (is|does|doesn't|isn't))\b.*\b(work|working)\b",
    ],
    # TIER 3: Premium
    TaskType.FEATURE: [
        r"\b(add|implement|build|develop)\b.*\b(feature|functionality|capability)\b",
        r"\b(new feature|enhancement|improvement)\b",
    ],
    TaskType.REFACTOR: [
        r"\b(refactor|restructure|reorganize|clean up|improve)\b.*\b(code|codebase)\b",
        r"\b(code smell|technical debt|optimization)\b",
    ],
    TaskType.COMPLEX: [
        r"\b(complex|complicated|advanced|sophisticated)\b",
        r"\b(multi-step|multiple steps|several parts)\b",
    ],
    # TIER 4: Premium+
    TaskType.ARCHITECTURE: [
        r"\b(architect|architecture|design|system design)\b",
        r"\b(infrastructure|scalability|microservices|distributed)\b",
        r"\b(adr|decision record|technical decision)\b",
    ],
    TaskType.RESEARCH: [
        r"\b(research|investigate|explore|deep dive)\b",
        r"\b(מחקר|חקור|בדוק לעומק)\b",
        r"\b(state of the art|best practices|industry standard)\b",
    ],
    TaskType.CRITICAL: [
        r"\b(critical|crucial|important|security|sensitive)\b.*\b(decision|change)\b",
        r"\b(production|deployment|release)\b.*\b(decision|approval)\b",
    ],
}

# Tier mapping
TIER_MAPPING: dict[TaskType, Tier] = {
    TaskType.SIMPLE: Tier.ULTRA_CHEAP,
    TaskType.TRANSLATE: Tier.ULTRA_CHEAP,
    TaskType.SUMMARIZE: Tier.ULTRA_CHEAP,
    TaskType.FORMAT: Tier.ULTRA_CHEAP,
    TaskType.CODING: Tier.ULTRA_CHEAP,  # DeepSeek is ultra-cheap
    TaskType.MATH: Tier.ULTRA_CHEAP,
    TaskType.DATA: Tier.ULTRA_CHEAP,
    TaskType.ANALYSIS: Tier.BUDGET,
    TaskType.REVIEW: Tier.BUDGET,
    TaskType.DEBUG: Tier.BUDGET,
    TaskType.FEATURE: Tier.PREMIUM,
    TaskType.REFACTOR: Tier.PREMIUM,
    TaskType.COMPLEX: Tier.PREMIUM,
    TaskType.ARCHITECTURE: Tier.PREMIUM_PLUS,
    TaskType.RESEARCH: Tier.BUDGET,  # DeepSeek R1 is budget
    TaskType.CRITICAL: Tier.PREMIUM_PLUS,
    TaskType.GENERAL: Tier.BUDGET,
}

# Model mapping
MODEL_MAPPING: dict[TaskType, str] = {
    TaskType.SIMPLE: "gemini-flash",
    TaskType.TRANSLATE: "gemini-flash",
    TaskType.SUMMARIZE: "gemini-flash",
    TaskType.FORMAT: "gemini-flash",
    TaskType.CODING: "deepseek-v3",
    TaskType.MATH: "deepseek-v3",
    TaskType.DATA: "gpt-4o-mini",
    TaskType.ANALYSIS: "claude-haiku",
    TaskType.REVIEW: "claude-haiku",
    TaskType.DEBUG: "claude-haiku",
    TaskType.FEATURE: "claude-sonnet",
    TaskType.REFACTOR: "claude-sonnet",
    TaskType.COMPLEX: "claude-sonnet",
    TaskType.ARCHITECTURE: "claude-opus",
    TaskType.RESEARCH: "deepseek-r1",
    TaskType.CRITICAL: "claude-opus",
    TaskType.GENERAL: "claude-haiku",
}


class TaskClassifier:
    """Classifies tasks to determine optimal model selection.

    Uses pattern matching for fast, cost-free classification.
    No LLM calls needed - pure heuristics.

    Example:
        classifier = TaskClassifier()
        result = classifier.classify("Write a Python function to sort a list")
        print(f"Task: {result.task_type}, Model: {result.suggested_model}")
        # Task: TaskType.CODING, Model: deepseek-v3
    """

    def __init__(self, patterns: dict[TaskType, list[str]] | None = None):
        """Initialize the classifier.

        Args:
            patterns: Custom patterns (uses defaults if None)
        """
        self.patterns = patterns or TASK_PATTERNS

        # Compile patterns for efficiency
        self._compiled: dict[TaskType, list[re.Pattern]] = {}
        for task_type, pattern_list in self.patterns.items():
            self._compiled[task_type] = [
                re.compile(p, re.IGNORECASE) for p in pattern_list
            ]

    def classify(self, prompt: str, context: str = "") -> ClassificationResult:
        """Classify a prompt to determine task type.

        Args:
            prompt: User prompt to classify
            context: Additional context (conversation history)

        Returns:
            ClassificationResult with task type, tier, confidence, and model
        """
        combined_text = f"{context}\n{prompt}" if context else prompt
        combined_text = combined_text.lower()

        # Track matches per task type
        matches: dict[TaskType, int] = {t: 0 for t in TaskType}
        matched_patterns: dict[TaskType, list[str]] = {t: [] for t in TaskType}

        # Check all patterns
        for task_type, compiled_patterns in self._compiled.items():
            for pattern in compiled_patterns:
                if pattern.search(combined_text):
                    matches[task_type] += 1
                    matched_patterns[task_type].append(pattern.pattern)

        # Find best match
        best_type = TaskType.GENERAL
        best_count = 0

        for task_type, count in matches.items():
            if count > best_count:
                best_count = count
                best_type = task_type

        # Calculate confidence
        if best_count == 0:
            confidence = 0.3  # Low confidence default
            reason = "No patterns matched, using default"
        elif best_count == 1:
            confidence = 0.6
            reason = f"Matched pattern: {matched_patterns[best_type][0]}"
        elif best_count == 2:
            confidence = 0.8
            reason = f"Matched {best_count} patterns"
        else:
            confidence = 0.95
            reason = f"Strong match: {best_count} patterns"

        return ClassificationResult(
            task_type=best_type,
            tier=TIER_MAPPING.get(best_type, Tier.BUDGET),
            confidence=confidence,
            reason=reason,
            suggested_model=MODEL_MAPPING.get(best_type, "claude-haiku"),
        )

    def classify_batch(
        self, prompts: list[str]
    ) -> list[ClassificationResult]:
        """Classify multiple prompts.

        Args:
            prompts: List of prompts to classify

        Returns:
            List of ClassificationResults
        """
        return [self.classify(prompt) for prompt in prompts]

    def get_tier(self, task_type: TaskType) -> Tier:
        """Get the cost tier for a task type.

        Args:
            task_type: Task type

        Returns:
            Cost tier
        """
        return TIER_MAPPING.get(task_type, Tier.BUDGET)

    def get_model(self, task_type: TaskType) -> str:
        """Get the suggested model for a task type.

        Args:
            task_type: Task type

        Returns:
            Model name
        """
        return MODEL_MAPPING.get(task_type, "claude-haiku")
