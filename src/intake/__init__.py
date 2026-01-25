"""Zero-Loss Intake System for Personal AI.

This module implements the intake layer that ensures no user input is ever lost.
Based on ADR-009 Research Integration + External Research 2026 validation.

Components:
- queue.py: Redis Streams wrapper for event sourcing
- outbox.py: Transactional Outbox pattern for reliability
- domain_classifier.py: Personal/Business/Mixed classification
- product_detector.py: Identifies when personal needs could become products

Architecture:
    User Input → Queue (Redis Streams) → Domain Classifier → Router
                      ↓
                 Outbox (PostgreSQL) → Guaranteed delivery

Principles (from alignment prompt):
- Zero input loss: Nothing the user sends is swallowed
- Self-sorting: Auto-classify personal/business/mixed
- Product detection: Flag personal needs with product potential
"""

from src.intake.domain_classifier import (
    Domain,
    DomainClassification,
    DomainClassifier,
)
from src.intake.product_detector import (
    ProductPotential,
    ProductDetector,
)
from src.intake.queue import (
    IntakeEvent,
    IntakeQueue,
)
from src.intake.outbox import (
    OutboxEntry,
    TransactionalOutbox,
)

__all__ = [
    # Domain Classification
    "Domain",
    "DomainClassification",
    "DomainClassifier",
    # Product Detection
    "ProductPotential",
    "ProductDetector",
    # Queue
    "IntakeEvent",
    "IntakeQueue",
    # Outbox
    "OutboxEntry",
    "TransactionalOutbox",
]
