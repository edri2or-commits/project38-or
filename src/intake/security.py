"""Security Guard module for the intake system.

Implements security patterns from External Research 2026 §4:
- Prompt injection detection (Acuvity-style patterns)
- Human-in-the-Loop for borderline cases
- "No Free Lunch" principle: Favor user confirmation over silent blocking

Key insight from research:
"No guardrail system can simultaneously minimize risk, maintain high utility,
and avoid usability loss. The architectural decision must favor Human-in-the-Loop
for borderline cases rather than silent blocking."

Sandbox Status:
- Pyodide: ❌ UNSAFE (CVE-2025-68668, CVSS 9.9)
- Firecracker: ✅ Recommended but requires KVM (not available on Railway)
- Integration path: Cloud Run / Modal.com / E2B.dev for code execution
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class ThreatLevel(str, Enum):
    """Threat level classification."""

    SAFE = "safe"           # No threats detected
    LOW = "low"             # Minor concerns, proceed with caution
    MEDIUM = "medium"       # Suspicious, recommend HITL confirmation
    HIGH = "high"           # Likely threat, block or require confirmation
    CRITICAL = "critical"   # Definite threat, block immediately


class ThreatType(str, Enum):
    """Types of security threats."""

    PROMPT_INJECTION = "prompt_injection"
    CODE_INJECTION = "code_injection"
    DATA_EXFILTRATION = "data_exfiltration"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    SENSITIVE_DATA = "sensitive_data"
    MALICIOUS_URL = "malicious_url"


@dataclass
class ThreatDetection:
    """Result of threat detection."""

    threat_level: ThreatLevel
    threat_type: ThreatType | None = None
    confidence: float = 0.0  # 0.0 to 1.0

    # Detection details
    matched_patterns: list[str] = field(default_factory=list)
    reasoning: str = ""

    # Action recommendation
    action: str = "proceed"  # proceed, confirm, block
    requires_hitl: bool = False

    # Metadata
    detected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class HITLRequest:
    """Human-in-the-Loop confirmation request."""

    request_id: str
    original_input: str
    threat_detection: ThreatDetection

    # User-facing message
    message_hebrew: str = ""
    message_english: str = ""

    # Options
    options: list[str] = field(default_factory=lambda: ["approve", "reject", "modify"])
    timeout_seconds: int = 300  # 5 minutes

    # Response
    user_response: str | None = None
    responded_at: str | None = None


class PromptInjectionDetector:
    """Detects prompt injection attacks.

    Based on External Research 2026 §4.1.1:
    - Semantic understanding to distinguish malicious intent from benign technical language
    - Zero false positives on technical domains (coding queries like "kill process")
    - Patterns for both direct and indirect injection

    Key patterns detected:
    1. Instruction override attempts ("ignore previous", "disregard system")
    2. Role manipulation ("you are now", "act as if")
    3. Output format hijacking ("respond only with", "output JSON")
    4. Context escape attempts (markdown/code block abuse)
    5. Indirect injection via RAG/external content
    """

    # Direct injection patterns - attempts to override instructions
    OVERRIDE_PATTERNS = [
        r"ignore (all |your |previous |the )?instructions",
        r"disregard (all |your |previous |the )?(instructions|rules|guidelines)",
        r"forget (all |your |previous |everything)",
        r"override (your |the )?(system|instructions|rules)",
        r"bypass (your |the )?(safety|security|restrictions)",
        r"התעלם מכל ההוראות",
        r"שכח את כל ההנחיות",
        r"בטל את כל הכללים",
    ]

    # Role manipulation - attempts to change AI behavior
    ROLE_PATTERNS = [
        r"you are now (a |an )?(?!helpful|assistant)",
        r"act as (if you are|though you were|a|an)",
        r"pretend (to be|you are|that you)",
        r"roleplay as",
        r"from now on,? you (are|will|must)",
        r"אתה עכשיו",
        r"התנהג כאילו אתה",
        r"מעכשיו אתה",
    ]

    # Output hijacking - attempts to control response format maliciously
    OUTPUT_PATTERNS = [
        r"respond (only |exclusively )?(with|in) (json|xml|code)",
        r"output (only|just|nothing but)",
        r"your (only |entire )?response (should|must|will) be",
        r"say (only|just|nothing but)",
        r"print (the |your )?(secret|password|key|token)",
        r"הדפס (את )?הסיסמה",
        r"תגיד רק",
    ]

    # Context escape - attempts to break out of context
    ESCAPE_PATTERNS = [
        r"```.*system.*```",
        r"\[SYSTEM\]",
        r"<\|im_start\|>",
        r"<\|endoftext\|>",
        r"###\s*(instruction|system)",
        r"human:\s*assistant:",
    ]

    # Data exfiltration - attempts to extract sensitive info
    EXFIL_PATTERNS = [
        r"(show|reveal|display|print|output) (the |your |all )?(secret|password|key|token|credential|api.?key)",
        r"what (is|are) (the |your )?(secret|password|api.?key)",
        r"(list|enumerate) (all |your )?(secret|credential|key)",
        r"מה הסיסמה",
        r"תראה לי את המפתח",
    ]

    # Benign technical patterns - should NOT trigger (reduce false positives)
    BENIGN_PATTERNS = [
        r"kill (-9 )?(\d+|process|pid)",  # Process management
        r"terminate (the )?(process|thread|connection)",
        r"drop (table|database|index)",  # SQL (in context of learning/coding)
        r"injection (attack|vulnerability|prevention)",  # Security education
        r"prompt injection (example|detection|prevention)",  # Meta-discussion
    ]

    # Confidence thresholds
    HITL_THRESHOLD = 0.6  # Request user confirmation above this
    BLOCK_THRESHOLD = 0.85  # Block without confirmation above this

    def __init__(self):
        """Initialize detector with compiled patterns."""
        self._compiled_threats = {
            "override": [re.compile(p, re.IGNORECASE) for p in self.OVERRIDE_PATTERNS],
            "role": [re.compile(p, re.IGNORECASE) for p in self.ROLE_PATTERNS],
            "output": [re.compile(p, re.IGNORECASE) for p in self.OUTPUT_PATTERNS],
            "escape": [re.compile(p, re.IGNORECASE) for p in self.ESCAPE_PATTERNS],
            "exfil": [re.compile(p, re.IGNORECASE) for p in self.EXFIL_PATTERNS],
        }
        self._compiled_benign = [
            re.compile(p, re.IGNORECASE) for p in self.BENIGN_PATTERNS
        ]

    def detect(self, text: str, context: str = "") -> ThreatDetection:
        """Detect prompt injection attempts.

        Args:
            text: Input text to analyze
            context: Additional context (e.g., RAG content)

        Returns:
            ThreatDetection with level and recommendations
        """
        full_text = f"{text} {context}".lower()

        # Check for benign technical patterns first (reduce false positives)
        for pattern in self._compiled_benign:
            if pattern.search(full_text):
                # This looks like legitimate technical content
                return ThreatDetection(
                    threat_level=ThreatLevel.SAFE,
                    confidence=0.9,
                    reasoning="Benign technical content detected"
                )

        # Check threat patterns
        matches: dict[str, list[str]] = {}
        for category, patterns in self._compiled_threats.items():
            category_matches = []
            for pattern in patterns:
                found = pattern.findall(full_text)
                if found:
                    category_matches.extend(found if isinstance(found[0], str) else [str(f) for f in found])
            if category_matches:
                matches[category] = category_matches

        if not matches:
            return ThreatDetection(
                threat_level=ThreatLevel.SAFE,
                confidence=0.95,
                reasoning="No threat patterns detected"
            )

        # Calculate threat level based on matches
        threat_score = 0.0
        matched_patterns = []

        # Weight by category severity
        weights = {
            "override": 0.9,   # Very dangerous
            "escape": 0.85,   # Context manipulation
            "exfil": 0.8,     # Data extraction
            "role": 0.6,      # Role manipulation
            "output": 0.5,    # Output hijacking
        }

        for category, category_matches in matches.items():
            weight = weights.get(category, 0.5)
            threat_score = max(threat_score, weight)
            matched_patterns.extend([f"{category}: {m}" for m in category_matches[:2]])

        # Boost if multiple categories match
        if len(matches) >= 2:
            threat_score = min(threat_score + 0.15, 1.0)
        if len(matches) >= 3:
            threat_score = min(threat_score + 0.15, 1.0)

        # Determine threat level and action
        if threat_score >= self.BLOCK_THRESHOLD:
            threat_level = ThreatLevel.CRITICAL
            action = "block"
            requires_hitl = False  # Block immediately
        elif threat_score >= self.HITL_THRESHOLD:
            threat_level = ThreatLevel.HIGH
            action = "confirm"
            requires_hitl = True
        elif threat_score >= 0.4:
            threat_level = ThreatLevel.MEDIUM
            action = "confirm"
            requires_hitl = True
        else:
            threat_level = ThreatLevel.LOW
            action = "proceed"
            requires_hitl = False

        return ThreatDetection(
            threat_level=threat_level,
            threat_type=ThreatType.PROMPT_INJECTION,
            confidence=threat_score,
            matched_patterns=matched_patterns,
            reasoning=f"Detected {len(matches)} threat categories: {', '.join(matches.keys())}",
            action=action,
            requires_hitl=requires_hitl
        )


class SensitiveDataDetector:
    """Detects potential sensitive data in inputs/outputs.

    Prevents accidental exposure of:
    - API keys and tokens
    - Passwords and credentials
    - Personal identifiable information (PII)
    - Financial data
    """

    PATTERNS = {
        "api_key": [
            r"(sk-|pk-|api[_-]?key[=:]\s*)['\"]?[a-zA-Z0-9]{20,}",
            r"(ANTHROPIC|OPENAI|GOOGLE|AWS)_?API[_-]?KEY",
            r"ghp_[a-zA-Z0-9]{36}",  # GitHub Personal Access Token
            r"gho_[a-zA-Z0-9]{36}",  # GitHub OAuth Token
        ],
        "password": [
            r"password[=:]\s*['\"]?[^\s'\"]{8,}",
            r"passwd[=:]\s*['\"]?[^\s'\"]{8,}",
            r"secret[=:]\s*['\"]?[^\s'\"]{8,}",
        ],
        "credit_card": [
            r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
        ],
        "israeli_id": [
            r"\b\d{9}\b",  # Israeli ID number (9 digits)
        ],
        "email": [
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        ],
    }

    def __init__(self):
        """Initialize detector."""
        self._compiled = {
            category: [re.compile(p, re.IGNORECASE) for p in patterns]
            for category, patterns in self.PATTERNS.items()
        }

    def detect(self, text: str) -> ThreatDetection:
        """Detect sensitive data in text.

        Args:
            text: Text to scan

        Returns:
            ThreatDetection with findings
        """
        matches: dict[str, list[str]] = {}

        for category, patterns in self._compiled.items():
            category_matches = []
            for pattern in patterns:
                found = pattern.findall(text)
                if found:
                    # Mask the actual values for security
                    category_matches.extend(["[REDACTED]"] * len(found))
            if category_matches:
                matches[category] = category_matches

        if not matches:
            return ThreatDetection(
                threat_level=ThreatLevel.SAFE,
                confidence=0.95,
                reasoning="No sensitive data detected"
            )

        # High severity for API keys and passwords
        high_severity = {"api_key", "password", "credit_card"}
        has_high_severity = bool(high_severity & set(matches.keys()))

        return ThreatDetection(
            threat_level=ThreatLevel.HIGH if has_high_severity else ThreatLevel.MEDIUM,
            threat_type=ThreatType.SENSITIVE_DATA,
            confidence=0.9 if has_high_severity else 0.7,
            matched_patterns=[f"{cat}: {len(m)} found" for cat, m in matches.items()],
            reasoning=f"Sensitive data detected: {', '.join(matches.keys())}",
            action="block" if has_high_severity else "confirm",
            requires_hitl=not has_high_severity
        )


class SecurityGuard:
    """Main security guard for the intake system.

    Combines multiple detectors and implements the HITL pattern.

    External Research 2026 §4.1.3 - "No Free Lunch" Theorem:
    "No guardrail can simultaneously minimize risk, maintain high utility,
    and avoid usability loss. Favor Human-in-the-Loop for borderline cases
    rather than silent blocking."
    """

    def __init__(
        self,
        hitl_callback: Callable[[HITLRequest], Awaitable[str]] | None = None,
        auto_block_critical: bool = True
    ):
        """Initialize security guard.

        Args:
            hitl_callback: Async callback for HITL requests (e.g., Telegram bot)
            auto_block_critical: Whether to auto-block critical threats
        """
        self._prompt_detector = PromptInjectionDetector()
        self._data_detector = SensitiveDataDetector()
        self._hitl_callback = hitl_callback
        self._auto_block_critical = auto_block_critical

    async def check(self, text: str, context: str = "") -> tuple[bool, ThreatDetection | None]:
        """Check input for security threats.

        Args:
            text: Input text
            context: Additional context

        Returns:
            Tuple of (is_safe, threat_detection)
        """
        # Check for prompt injection
        injection_result = self._prompt_detector.detect(text, context)

        # Check for sensitive data
        data_result = self._data_detector.detect(text)

        # Take the more severe result
        if injection_result.threat_level.value > data_result.threat_level.value:
            result = injection_result
        elif data_result.threat_level.value > injection_result.threat_level.value:
            result = data_result
        else:
            # Same level, prefer the one with HITL requirement
            result = injection_result if injection_result.requires_hitl else data_result

        # Handle based on threat level
        if result.threat_level == ThreatLevel.SAFE:
            return True, None

        if result.threat_level == ThreatLevel.CRITICAL and self._auto_block_critical:
            logger.warning(f"SecurityGuard: Blocked critical threat: {result.reasoning}")
            return False, result

        if result.requires_hitl and self._hitl_callback:
            # Request user confirmation
            approved = await self._request_hitl_confirmation(text, result)
            return approved, result

        # Low/medium without HITL - proceed with warning
        if result.threat_level in (ThreatLevel.LOW, ThreatLevel.MEDIUM):
            logger.info(f"SecurityGuard: Proceeding with caution: {result.reasoning}")
            return True, result

        # High without HITL callback - block
        return False, result

    async def _request_hitl_confirmation(
        self,
        text: str,
        detection: ThreatDetection
    ) -> bool:
        """Request Human-in-the-Loop confirmation.

        Args:
            text: Original input
            detection: Threat detection result

        Returns:
            True if user approved, False otherwise
        """
        from uuid import uuid4

        request = HITLRequest(
            request_id=str(uuid4()),
            original_input=text[:500],  # Truncate for display
            threat_detection=detection,
            message_hebrew=f"⚠️ זוהה תוכן חשוד ({detection.threat_level.value})\n"
                          f"סיבה: {detection.reasoning}\n"
                          f"האם לאשר את הפעולה?",
            message_english=f"⚠️ Suspicious content detected ({detection.threat_level.value})\n"
                           f"Reason: {detection.reasoning}\n"
                           f"Do you want to proceed?"
        )

        try:
            response = await self._hitl_callback(request)
            return response.lower() in ("approve", "yes", "כן", "אשר")
        except Exception as e:
            logger.error(f"HITL callback failed: {e}")
            # Fail closed - deny if HITL fails
            return False

    def check_sync(self, text: str, context: str = "") -> tuple[bool, ThreatDetection | None]:
        """Synchronous version of check (without HITL).

        Args:
            text: Input text
            context: Additional context

        Returns:
            Tuple of (is_safe, threat_detection)
        """
        injection_result = self._prompt_detector.detect(text, context)
        data_result = self._data_detector.detect(text)

        # Take more severe result
        if injection_result.threat_level.value >= data_result.threat_level.value:
            result = injection_result
        else:
            result = data_result

        if result.threat_level == ThreatLevel.SAFE:
            return True, None

        if result.threat_level == ThreatLevel.CRITICAL:
            return False, result

        # Without async HITL, proceed with warning for non-critical
        return True, result
