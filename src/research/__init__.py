"""Research integration module for ADR-009 Phase 5.

This module provides autonomous research processing capabilities:
- Research note classification (classifier.py)
- Research ingestion from minimal input (ingestion_agent.py)
- Automatic experiment creation (experiment_creator.py)

Architecture Decision: ADR-009 Research Integration Architecture
"""

from src.research.classifier import (
    Classification,
    Effort,
    ImpactScope,
    ResearchNote,
    Risk,
    auto_classify,
    find_unclassified_notes,
    parse_research_note,
    update_note_with_classification,
)
from src.research.experiment_creator import (
    ExperimentConfig,
    create_experiment_for_note,
    create_experiment_skeleton,
    get_next_experiment_id,
)
from src.research.ingestion_agent import (
    InferredFields,
    ResearchInput,
    create_research_note,
    ingest_research,
    parse_user_prompt,
)

__all__ = [
    # Classifier
    "Classification",
    "Effort",
    "ImpactScope",
    "ResearchNote",
    "Risk",
    "auto_classify",
    "find_unclassified_notes",
    "parse_research_note",
    "update_note_with_classification",
    # Experiment Creator
    "ExperimentConfig",
    "create_experiment_for_note",
    "create_experiment_skeleton",
    "get_next_experiment_id",
    # Ingestion Agent
    "InferredFields",
    "ResearchInput",
    "create_research_note",
    "ingest_research",
    "parse_user_prompt",
]
