# Intake API Reference

The Intake module implements a Zero-Loss Intake System ensuring no user input is ever lost. Based on ADR-009 Research Integration + External Research 2026 validation.

## Overview

```
User Input → Queue (Redis Streams) → Domain Classifier → Router
                  ↓
             Outbox (PostgreSQL) → Guaranteed delivery
```

**Core Principles**:
- **Zero input loss**: Nothing the user sends is swallowed
- **Self-sorting**: Auto-classify personal/business/mixed
- **Product detection**: Flag personal needs with product potential
- **Security as base requirement**: Prompt injection detection with HITL

## Module Structure

```
src/intake/
├── __init__.py           # Package exports (40+ classes/enums)
├── queue.py              # Redis Streams wrapper for event sourcing
├── outbox.py             # Transactional Outbox pattern
├── domain_classifier.py  # Personal/Business/Mixed classification
├── product_detector.py   # Product potential identification
├── classifier.py         # Unified cascade classifier with Inter-Cascade
├── security.py           # Security guard with HITL support
├── adhd_ux.py            # ADHD-friendly UX patterns
└── governance.py         # ADR Writer & Research Gate
```

## Queue Module

::: src.intake.queue
    options:
        show_root_heading: true
        heading_level: 3

### IntakeEvent

Immutable event stored in Redis Streams.

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | `str` | UUID v4 identifier |
| `event_type` | `EventType` | Type of event (USER_MESSAGE, CLASSIFICATION_COMPLETE, etc.) |
| `payload` | `dict` | Event data |
| `timestamp` | `datetime` | When event was created |
| `metadata` | `dict` | Additional context |

### EventType

```python
class EventType(str, Enum):
    USER_MESSAGE = "user_message"
    USER_FILE = "user_file"
    USER_VOICE = "user_voice"
    CLASSIFICATION_COMPLETE = "classification_complete"
    ROUTING_DECISION = "routing_decision"
    PROCESSING_STARTED = "processing_started"
    PROCESSING_COMPLETE = "processing_complete"
    PROCESSING_FAILED = "processing_failed"
    RETRY_SCHEDULED = "retry_scheduled"
```

### IntakeQueue

Redis Streams wrapper providing:
- `publish(event)` - Add event to stream
- `consume(consumer_group, consumer_name)` - Consume events
- `ack(event_id)` - Acknowledge processing complete

## Outbox Module

::: src.intake.outbox
    options:
        show_root_heading: true
        heading_level: 3

### TransactionalOutbox

Implements the Transactional Outbox pattern for guaranteed message delivery.

| Method | Description |
|--------|-------------|
| `save(entry)` | Atomically save with business transaction |
| `mark_sent(entry_id)` | Mark as successfully delivered |
| `get_pending()` | Get unsent entries for retry |
| `cleanup_old(days)` | Remove old processed entries |

## Domain Classifier Module

::: src.intake.domain_classifier
    options:
        show_root_heading: true
        heading_level: 3

### Domain

```python
class Domain(str, Enum):
    PERSONAL = "personal"   # Personal life: health, family, hobbies
    BUSINESS = "business"   # Work: project38-or, code, deployment
    MIXED = "mixed"         # Overlapping concerns
```

### DomainClassifier

Rule-based domain classification with keyword matching.

```python
classifier = DomainClassifier()
result = classifier.classify("I need to fix the deployment pipeline")
# result.domain = Domain.BUSINESS
# result.confidence = 0.8
```

## Product Detector Module

::: src.intake.product_detector
    options:
        show_root_heading: true
        heading_level: 3

### ProductPotential

Identifies when personal needs could become products.

| Field | Type | Description |
|-------|------|-------------|
| `is_potential` | `bool` | Has product potential |
| `score` | `float` | 0.0-1.0 confidence |
| `patterns` | `list[str]` | Matched patterns |
| `reasoning` | `str` | Why flagged |

## Classifier Module (Phase 2)

::: src.intake.classifier
    options:
        show_root_heading: true
        heading_level: 3

### Cascade Classification

Three-tier classification following External Research 2026:

1. **Rule-based** (fastest, free): Keyword matching
2. **Haiku 4.5** (fast, cheap): For ambiguous cases
3. **Sonnet 4.5** (accurate, expensive): For complex cases

```python
classifier = IntakeClassifier()
result = await classifier.classify("אני צריך לתקן את הבוט")
# Uses cascade: rules → haiku → sonnet based on confidence
```

### Inter-Cascade Learning

Strong model (Sonnet) teaches weak model (Haiku):

```python
# When Sonnet classifies with high confidence:
store.add_example(text, result.domain, source="sonnet")
# Haiku uses these as few-shot examples next time
```

### FewShotStore

Stores high-confidence examples for few-shot learning.

| Method | Description |
|--------|-------------|
| `add_example(text, label, source)` | Add new example |
| `get_examples(label, k)` | Get k examples for label |
| `get_all()` | Get all stored examples |

## Security Module (Phase 3)

::: src.intake.security
    options:
        show_root_heading: true
        heading_level: 3

### ThreatLevel

```python
class ThreatLevel(str, Enum):
    NONE = "none"           # Safe
    LOW = "low"             # Suspicious but likely safe
    MEDIUM = "medium"       # Requires review
    HIGH = "high"           # Block immediately
    CRITICAL = "critical"   # Block and alert
```

### ThreatType

```python
class ThreatType(str, Enum):
    PROMPT_INJECTION = "prompt_injection"
    SENSITIVE_DATA = "sensitive_data"
    MALICIOUS_CODE = "malicious_code"
    SOCIAL_ENGINEERING = "social_engineering"
```

### SecurityGuard

Main security coordinator with HITL support.

```python
guard = SecurityGuard()
result = await guard.check(user_input)

if result.needs_hitl:
    # Route to human review
    hitl_request = result.hitl_request
    # Wait for human decision
```

### PromptInjectionDetector

Acuvity-style detection with zero false positive goal.

Patterns detected:
- `ignore previous instructions`
- `you are now`
- `system prompt`
- Base64/hex encoded instructions
- Unicode obfuscation

### HITLRequest

Human-in-the-Loop request for borderline cases.

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | `str` | Unique request ID |
| `content` | `str` | Content to review |
| `threat_type` | `ThreatType` | Detected threat |
| `confidence` | `float` | Detection confidence |
| `context` | `dict` | Additional context |
| `expires_at` | `datetime` | Review deadline |

## ADHD UX Module (Phase 4)

::: src.intake.adhd_ux
    options:
        show_root_heading: true
        heading_level: 3

### FlowState

```python
class FlowState(str, Enum):
    IDLE = "idle"           # Not actively working
    SHALLOW = "shallow"     # Light work, interruptible
    FOCUSED = "focused"     # Working, minimize interrupts
    DEEP_FOCUS = "deep_focus"  # Critical work, block all
```

### InterruptionUrgency

```python
class InterruptionUrgency(str, Enum):
    LOW = "low"             # Can wait hours
    MEDIUM = "medium"       # Within 30 minutes
    HIGH = "high"           # Within 5 minutes
    CRITICAL = "critical"   # Immediate
```

### InterruptionManager

Context-aware notification delivery.

```python
manager = InterruptionManager(quiet_windows=[
    QuietWindow(start=time(22, 0), end=time(7, 0), name="night"),
])

delivered, pending = manager.process_notification(
    message="New email from boss",
    urgency=InterruptionUrgency.HIGH,
    context={"source": "gmail"}
)

if not delivered:
    # Notification queued for later
    print(f"Pending: {pending.message}")
```

### CognitiveLoadDetector

Estimates mental load 0.0-1.0 based on:
- Time since last break
- Recent interaction frequency
- Task complexity signals

### ProactiveEngagement

Gentle nudges when user might need help:
- Reminder nudges
- Check-in nudges
- Break suggestion nudges

### ADHDUXManager

Unified coordinator for all ADHD UX patterns.

```python
manager = ADHDUXManager()
manager.enter_focus_mode()  # Block non-critical

delivered, pending = manager.notify(
    message="Build failed",
    urgency=InterruptionUrgency.CRITICAL
)
# Critical messages bypass focus mode
```

## Governance Module (Phase 5)

::: src.intake.governance
    options:
        show_root_heading: true
        heading_level: 3

### ADRWriterAgent

Transforms scattered thoughts into structured ADRs.

9-step workflow (from ADR-011):
1. INTAKE - Parse raw request
2. SYSTEM_MAPPING - Investigate codebase
3. REALITY_CHECK - Compare expectation vs actual
4. DECISION_ANALYSIS - Present options
5. EXTERNAL_RESEARCH - Search best practices
6. PATTERN_HISTORY - Check past requests
7. IMPULSIVITY_CHECK - Detect impulse requests
8. PLAN - Create implementation plan
9. DELIVERABLE - Full ADR output

```python
agent = ADRWriterAgent()

# Check if input is decision-related
is_decision, confidence = agent.is_decision_related("צריך להחליט איך לעשות X")
# is_decision = True, confidence = 0.7

# Generate ADR
draft = await agent.generate_adr(
    user_input="אני רוצה שהבוט יהיה יותר חכם",
    context={"source": "telegram"}
)
```

### ResearchGate

Controls research integration pipeline (ADR-009 5-stage process).

```python
class ResearchStage(str, Enum):
    CAPTURE = "capture"       # Document discovery
    TRIAGE = "triage"         # Weekly review
    EXPERIMENT = "experiment" # Isolated test
    EVALUATE = "evaluate"     # Compare to baseline
    INTEGRATE = "integrate"   # Feature flag rollout
```

Decision Matrix:
| Quality | Latency | Cost | Decision |
|---------|---------|------|----------|
| Better | Better | Better | **ADOPT** |
| Worse | Any | Any | **REJECT** |
| Mixed | Mixed | Mixed | **DEFER** |

```python
gate = ResearchGate()

# Evaluate research
result = gate.evaluate(note, {
    "quality": "better",
    "latency": "same",
    "cost": "higher"
})
# result.decision = ResearchDecision.DEFER
```

### GovernanceRouter

Routes content to appropriate handlers.

```python
router = GovernanceRouter()
result = await router.route(user_input, context)

if result.handler == "adr_writer":
    # Decision-related content
    draft = result.adr_draft
elif result.handler == "research_gate":
    # Research content
    gate_result = result.research_result
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `REDIS_URL` | For queue | Redis connection string |
| `DATABASE_URL` | For outbox | PostgreSQL connection |
| `ANTHROPIC_API_KEY` | For classifier | Claude API access |
| `HITL_WEBHOOK_URL` | Optional | HITL notification endpoint |

## Usage Examples

### Basic Intake Flow

```python
from src.intake import (
    IntakeQueue,
    IntakeEvent,
    IntakeClassifier,
    SecurityGuard,
    ADHDUXManager,
)

# 1. Receive input
event = IntakeEvent.create(
    event_type=EventType.USER_MESSAGE,
    payload={"text": user_input}
)

# 2. Security check
guard = SecurityGuard()
security_result = await guard.check(user_input)

if security_result.threat_level >= ThreatLevel.HIGH:
    # Block dangerous content
    return {"error": "Content blocked"}

# 3. Classify
classifier = IntakeClassifier()
classification = await classifier.classify(user_input)

# 4. Check interruption timing
ux_manager = ADHDUXManager()
delivered, pending = ux_manager.notify(
    message=f"New {classification.domain.value} input",
    urgency=InterruptionUrgency.MEDIUM
)

# 5. Queue for processing
queue = IntakeQueue()
await queue.publish(event)
```

### Governance Routing

```python
from src.intake import GovernanceRouter

router = GovernanceRouter()
result = await router.route(
    "אני חושב שנוסיף תמיכה ב-Slack",
    context={"source": "telegram", "user_id": "123"}
)

if result.handler == "adr_writer":
    print(f"ADR generated: {result.adr_draft.title}")
```

## Testing

Tests are in `tests/test_intake.py` (65+ tests).

```bash
# Run all intake tests
pytest tests/test_intake.py -v

# Run specific phase tests
pytest tests/test_intake.py -k "adhd" -v
pytest tests/test_intake.py -k "governance" -v
```

## Related Documentation

- [ADR-009: Research Integration Architecture](../decisions/ADR-009-research-integration-architecture.md)
- [ADR-011: ADR Architect](../decisions/ADR-011-adr-architect-structured-request-processing.md)
- [External Research 2026 Validation](../research/notes/)
