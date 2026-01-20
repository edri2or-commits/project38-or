"""
Quality Metrics for Model Evaluation.

Provides metrics for measuring response quality:
- Keyword presence
- Format compliance (JSON, Markdown)
- Semantic similarity (basic)
- Response completeness

Architecture Decision: ADR-009
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class QualityMetrics:
    """Quality metrics for model responses.

    Attributes:
        keyword_score: Score based on expected keyword presence (0-1).
        format_score: Score based on format compliance (0-1).
        completeness_score: Score based on response length/completeness (0-1).
        overall_score: Weighted average of all scores (0-1).
        details: Detailed breakdown of metric calculation.
    """

    keyword_score: float = 0.0
    format_score: float = 0.0
    completeness_score: float = 0.0
    overall_score: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def calculate(
        cls,
        response: str,
        expected_keywords: list[str] | None = None,
        expected_format: str | None = None,
        min_length: int = 10,
        weights: dict[str, float] | None = None,
    ) -> "QualityMetrics":
        """Calculate quality metrics for a response.

        Args:
            response: The model's response text.
            expected_keywords: Keywords that should appear in response.
            expected_format: Expected format ('json', 'markdown', 'code').
            min_length: Minimum response length for completeness.
            weights: Custom weights for score components.

        Returns:
            QualityMetrics instance with calculated scores.
        """
        weights = weights or {
            "keyword": 0.4,
            "format": 0.3,
            "completeness": 0.3,
        }

        metrics = cls()
        metrics.details = {"weights": weights}

        # Keyword score
        if expected_keywords:
            metrics.keyword_score = cls._calculate_keyword_score(
                response, expected_keywords
            )
            metrics.details["keyword_hits"] = cls._get_keyword_hits(
                response, expected_keywords
            )
        else:
            metrics.keyword_score = 1.0  # No keywords to check
            metrics.details["keyword_hits"] = []

        # Format score
        if expected_format:
            metrics.format_score = cls._calculate_format_score(
                response, expected_format
            )
            metrics.details["format_check"] = expected_format
        else:
            metrics.format_score = 1.0  # No format to check
            metrics.details["format_check"] = None

        # Completeness score
        metrics.completeness_score = cls._calculate_completeness_score(
            response, min_length
        )
        metrics.details["response_length"] = len(response)

        # Overall weighted score
        metrics.overall_score = (
            metrics.keyword_score * weights["keyword"]
            + metrics.format_score * weights["format"]
            + metrics.completeness_score * weights["completeness"]
        )

        return metrics

    @staticmethod
    def _calculate_keyword_score(response: str, keywords: list[str]) -> float:
        """Calculate keyword presence score.

        Args:
            response: Response text.
            keywords: Expected keywords.

        Returns:
            Score between 0 and 1.
        """
        if not keywords:
            return 1.0

        response_lower = response.lower()
        hits = sum(1 for kw in keywords if kw.lower() in response_lower)
        return hits / len(keywords)

    @staticmethod
    def _get_keyword_hits(response: str, keywords: list[str]) -> list[str]:
        """Get list of keywords found in response.

        Args:
            response: Response text.
            keywords: Keywords to search for.

        Returns:
            List of found keywords.
        """
        response_lower = response.lower()
        return [kw for kw in keywords if kw.lower() in response_lower]

    @staticmethod
    def _calculate_format_score(response: str, expected_format: str) -> float:
        """Calculate format compliance score.

        Args:
            response: Response text.
            expected_format: Expected format type.

        Returns:
            Score between 0 and 1.
        """
        if expected_format == "json":
            return QualityMetrics._check_json_format(response)
        elif expected_format == "markdown":
            return QualityMetrics._check_markdown_format(response)
        elif expected_format == "code":
            return QualityMetrics._check_code_format(response)
        else:
            return 1.0  # Unknown format, assume OK

    @staticmethod
    def _check_json_format(response: str) -> float:
        """Check if response is valid JSON.

        Args:
            response: Response text.

        Returns:
            1.0 if valid JSON, 0.0 otherwise.
        """
        # Try to find JSON in response (may be wrapped in markdown)
        json_patterns = [
            response,  # Raw response
            re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL),
            re.search(r"```\s*([\[{].*?[\]}])\s*```", response, re.DOTALL),
        ]

        for pattern in json_patterns:
            text = pattern.group(1) if hasattr(pattern, "group") else pattern
            if text:
                try:
                    json.loads(text.strip() if isinstance(text, str) else text)
                    return 1.0
                except (json.JSONDecodeError, TypeError):
                    continue

        return 0.0

    @staticmethod
    def _check_markdown_format(response: str) -> float:
        """Check if response contains markdown formatting.

        Args:
            response: Response text.

        Returns:
            Score based on markdown indicators found.
        """
        indicators = [
            (r"^#{1,6}\s", 0.3),  # Headers
            (r"```", 0.2),  # Code blocks
            (r"\*\*.*?\*\*", 0.2),  # Bold
            (r"^\s*[-*]\s", 0.15),  # Lists
            (r"^\s*\d+\.\s", 0.15),  # Numbered lists
        ]

        score = 0.0
        for pattern, weight in indicators:
            if re.search(pattern, response, re.MULTILINE):
                score += weight

        return min(score, 1.0)

    @staticmethod
    def _check_code_format(response: str) -> float:
        """Check if response contains code.

        Args:
            response: Response text.

        Returns:
            Score based on code indicators found.
        """
        indicators = [
            (r"```\w*\n", 0.4),  # Code blocks with language
            (r"def\s+\w+\(", 0.2),  # Python functions
            (r"class\s+\w+", 0.2),  # Classes
            (r"import\s+\w+", 0.1),  # Imports
            (r"return\s+", 0.1),  # Return statements
        ]

        score = 0.0
        for pattern, weight in indicators:
            if re.search(pattern, response):
                score += weight

        return min(score, 1.0)

    @staticmethod
    def _calculate_completeness_score(response: str, min_length: int) -> float:
        """Calculate response completeness score.

        Args:
            response: Response text.
            min_length: Minimum expected length.

        Returns:
            Score between 0 and 1.
        """
        if not response:
            return 0.0

        length = len(response.strip())

        if length >= min_length * 2:
            return 1.0
        elif length >= min_length:
            return 0.8
        elif length >= min_length / 2:
            return 0.5
        else:
            return 0.2

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation.
        """
        return {
            "keyword_score": self.keyword_score,
            "format_score": self.format_score,
            "completeness_score": self.completeness_score,
            "overall_score": self.overall_score,
            "details": self.details,
        }
