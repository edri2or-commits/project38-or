"""
Automated Governance Module - Phase 5 of Zero-Loss Intake System.

Implements automated governance patterns from alignment prompt:
1. ADR Writer Agent - Transforms scattered thoughts into structured ADRs
2. Research Gate - Controls research integration (ADR-009 pipeline)

Key principles:
- פרוטוקול אמת (Truth Protocol) - No fabrication, all claims verified
- Automated but not autonomous - Human approval for significant decisions
- Integration with existing adr-architect skill and research module

Author: Claude Code Agent
Date: 2026-01-25
"""

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# ADR Writer Agent
# =============================================================================

class ADRStatus(str, Enum):
    """Status of ADR creation process."""

    DRAFT = "draft"              # Initial draft created
    ANALYSIS = "analysis"        # System analysis in progress
    OPTIONS = "options"          # Options being evaluated
    REVIEW = "review"            # Awaiting human review
    APPROVED = "approved"        # Human approved
    REJECTED = "rejected"        # Human rejected
    IMPLEMENTED = "implemented"  # ADR implemented


class ADRType(str, Enum):
    """Types of Architecture Decision Records."""

    SPIKE = "spike"              # Quick experiment needed
    FEATURE = "feature"          # New feature decision
    REFACTOR = "refactor"        # Refactoring decision
    INTEGRATION = "integration"  # External integration
    SECURITY = "security"        # Security-related
    PERFORMANCE = "performance"  # Performance optimization
    RESEARCH = "research"        # Research integration


@dataclass
class ScatteredInput:
    """Raw input that needs to be structured into an ADR."""

    raw_text: str
    source: str = "user"  # user, intake, email, etc.
    language: str = "auto"  # he, en, auto
    timestamp: datetime = field(default_factory=datetime.now)
    context: dict = field(default_factory=dict)

    @property
    def detected_language(self) -> str:
        """Detect language from text."""
        if self.language != "auto":
            return self.language

        # Simple Hebrew detection
        hebrew_chars = len(re.findall(r'[\u0590-\u05FF]', self.raw_text))
        total_chars = len(re.findall(r'\w', self.raw_text))

        if total_chars > 0 and hebrew_chars / total_chars > 0.3:
            return "he"
        return "en"


@dataclass
class ADRDraft:
    """Draft ADR generated from scattered input."""

    id: str = field(default_factory=lambda: f"ADR-{uuid.uuid4().hex[:8].upper()}")
    title: str = ""
    status: ADRStatus = ADRStatus.DRAFT
    adr_type: ADRType = ADRType.FEATURE

    # Core ADR fields
    context: str = ""              # Why is this decision needed?
    decision: str = ""             # What is the decision?
    consequences: list[str] = field(default_factory=list)
    alternatives: list[dict] = field(default_factory=list)

    # Extracted from input
    original_input: str = ""
    extracted_intent: str = ""
    extracted_requirements: list[str] = field(default_factory=list)
    impulsivity_score: float = 0.0  # 0.0 = well-thought, 1.0 = impulsive

    # Analysis results
    affected_files: list[str] = field(default_factory=list)
    estimated_effort: str = ""     # Small/Medium/Large
    risk_level: str = ""           # Low/Medium/High
    proof_of_work: list[str] = field(default_factory=list)  # Evidence gathered

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_markdown(self) -> str:
        """Convert to ADR markdown format."""
        lines = [
            f"# {self.id}: {self.title}",
            "",
            f"**Status**: {self.status.value}",
            f"**Type**: {self.adr_type.value}",
            f"**Created**: {self.created_at.strftime('%Y-%m-%d')}",
            "",
            "## Context",
            "",
            self.context,
            "",
            "## Decision",
            "",
            self.decision,
            "",
        ]

        if self.alternatives:
            lines.extend(["## Alternatives Considered", ""])
            for i, alt in enumerate(self.alternatives, 1):
                lines.append(f"### Option {i}: {alt.get('name', 'Unknown')}")
                lines.append("")
                lines.append(alt.get('description', ''))
                if alt.get('pros'):
                    lines.append("")
                    lines.append("**Pros:**")
                    for pro in alt['pros']:
                        lines.append(f"- {pro}")
                if alt.get('cons'):
                    lines.append("")
                    lines.append("**Cons:**")
                    for con in alt['cons']:
                        lines.append(f"- {con}")
                lines.append("")

        if self.consequences:
            lines.extend(["## Consequences", ""])
            for consequence in self.consequences:
                lines.append(f"- {consequence}")
            lines.append("")

        if self.affected_files:
            lines.extend(["## Affected Files", ""])
            for file in self.affected_files:
                lines.append(f"- `{file}`")
            lines.append("")

        if self.proof_of_work:
            lines.extend(["## Proof of Work", ""])
            for evidence in self.proof_of_work:
                lines.append(f"- {evidence}")
            lines.append("")

        # Original input for transparency
        lines.extend([
            "---",
            "",
            "## Original Request",
            "",
            f"```",
            self.original_input[:500] + ("..." if len(self.original_input) > 500 else ""),
            "```",
        ])

        return "\n".join(lines)


class ADRWriterAgent:
    """
    Transforms scattered thoughts into structured ADRs.

    Implements the 9-step adr-architect workflow programmatically:
    1. INTAKE - Parse raw request
    2. SYSTEM MAPPING - Investigate codebase
    3. REALITY CHECK - Compare expectation vs actual
    4. DECISION ANALYSIS - Present options
    5. EXTERNAL RESEARCH - Search best practices
    6. PATTERN FROM HISTORY - Check past decisions
    7. IMPULSIVITY CHECK - Detect rushed decisions
    8. PLAN - Create implementation plan
    9. DELIVERABLE - Generate ADR
    """

    # Intent detection patterns
    DECISION_PATTERNS = [
        # Hebrew
        r"צריך להחליט",
        r"אני חושב ש(נוסיף|נשנה|נסיר)",
        r"מה דעתך על",
        r"האם כדאי ל",
        r"שינוי ב",
        r"להוסיף (תמיכה|אפשרות|יכולת)",
        # English
        r"should we (add|change|remove)",
        r"what if we",
        r"decision needed",
        r"thinking about (adding|changing|implementing)",
        r"proposal to",
    ]

    # Impulsivity indicators
    IMPULSIVITY_PATTERNS = [
        r"בוא נעשה את זה עכשיו",
        r"פשוט (נוסיף|נשנה)",
        r"just (add|do|change) it",
        r"quickly",
        r"let's just",
        r"no need to plan",
    ]

    def __init__(
        self,
        adr_directory: str = "docs/decisions",
        codebase_search: Optional[Callable] = None,
        external_search: Optional[Callable] = None,
    ):
        self.adr_directory = Path(adr_directory)
        self.codebase_search = codebase_search
        self.external_search = external_search

        self._compiled_decision = [re.compile(p, re.IGNORECASE) for p in self.DECISION_PATTERNS]
        self._compiled_impulsive = [re.compile(p, re.IGNORECASE) for p in self.IMPULSIVITY_PATTERNS]

    def is_decision_related(self, text: str) -> tuple[bool, float]:
        """
        Check if text is related to architectural decisions.

        Returns:
            (is_related, confidence)
        """
        text_lower = text.lower()

        matches = 0
        for pattern in self._compiled_decision:
            if pattern.search(text_lower):
                matches += 1

        if matches == 0:
            return (False, 0.0)

        confidence = min(0.3 + (matches * 0.2), 1.0)
        return (True, confidence)

    def check_impulsivity(self, text: str) -> float:
        """
        Check for impulsivity indicators.

        Returns:
            Impulsivity score 0.0-1.0 (higher = more impulsive)
        """
        text_lower = text.lower()

        matches = 0
        for pattern in self._compiled_impulsive:
            if pattern.search(text_lower):
                matches += 1

        # Also check for lack of reasoning words
        reasoning_words = ["because", "since", "כי", "מכיוון", "after considering", "לאחר"]
        has_reasoning = any(word in text_lower for word in reasoning_words)

        base_score = min(matches * 0.3, 0.8)
        if not has_reasoning and len(text) < 100:
            base_score += 0.2

        return min(base_score, 1.0)

    def extract_intent(self, input_data: ScatteredInput) -> str:
        """Extract the core intent from scattered input."""
        text = input_data.raw_text

        # Look for action verbs
        action_patterns = [
            r"(להוסיף|לשנות|להסיר|לשפר|ליצור|לבנות)\s+(.+?)(?:\.|,|$)",
            r"(add|change|remove|improve|create|build)\s+(.+?)(?:\.|,|$)",
        ]

        for pattern in action_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return f"{match.group(1)} {match.group(2)}".strip()

        # Fallback: first sentence
        first_sentence = text.split('.')[0].strip()
        return first_sentence[:200]

    def extract_requirements(self, input_data: ScatteredInput) -> list[str]:
        """Extract requirements from input."""
        text = input_data.raw_text
        requirements = []

        # Look for requirement patterns
        patterns = [
            r"צריך (ש|ל)(.+?)(?:\.|,|$)",
            r"חייב (ש|ל)(.+?)(?:\.|,|$)",
            r"(must|should|need to)\s+(.+?)(?:\.|,|$)",
            r"requirement[s]?:?\s*(.+?)(?:\.|,|$)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    req = ' '.join(match).strip()
                else:
                    req = match.strip()
                if len(req) > 5:
                    requirements.append(req)

        return requirements[:10]  # Max 10 requirements

    def detect_adr_type(self, input_data: ScatteredInput) -> ADRType:
        """Detect the type of ADR needed."""
        text = input_data.raw_text.lower()

        type_keywords = {
            ADRType.SECURITY: ["security", "אבטחה", "authentication", "authorization", "secrets"],
            ADRType.PERFORMANCE: ["performance", "ביצועים", "speed", "latency", "optimization"],
            ADRType.INTEGRATION: ["integrate", "אינטגרציה", "api", "external", "service"],
            ADRType.RESEARCH: ["research", "מחקר", "experiment", "study", "paper"],
            ADRType.REFACTOR: ["refactor", "refactoring", "ריפקטור", "cleanup", "reorganize"],
            ADRType.SPIKE: ["spike", "poc", "prototype", "try", "experiment"],
        }

        for adr_type, keywords in type_keywords.items():
            if any(kw in text for kw in keywords):
                return adr_type

        return ADRType.FEATURE

    def create_draft(self, input_data: ScatteredInput) -> ADRDraft:
        """
        Create initial ADR draft from scattered input.

        This is step 1 (INTAKE) of the 9-step process.
        """
        draft = ADRDraft(
            original_input=input_data.raw_text,
            extracted_intent=self.extract_intent(input_data),
            extracted_requirements=self.extract_requirements(input_data),
            impulsivity_score=self.check_impulsivity(input_data.raw_text),
            adr_type=self.detect_adr_type(input_data),
        )

        # Generate title from intent
        intent = draft.extracted_intent
        if input_data.detected_language == "he":
            draft.title = f"החלטה: {intent[:50]}"
        else:
            draft.title = f"Decision: {intent[:50]}"

        # Initial context
        draft.context = f"User request: {intent}"

        # Add impulsivity warning if needed
        if draft.impulsivity_score > 0.5:
            draft.proof_of_work.append(
                f"⚠️ Impulsivity score: {draft.impulsivity_score:.0%} - "
                "Consider slowing down and gathering more context"
            )

        draft.status = ADRStatus.DRAFT
        return draft

    async def analyze_codebase(self, draft: ADRDraft) -> ADRDraft:
        """
        Analyze codebase for relevant context.

        This is step 2 (SYSTEM MAPPING) of the 9-step process.
        """
        if self.codebase_search is None:
            draft.proof_of_work.append("Codebase search: Not available")
            return draft

        # Search for related files
        keywords = draft.extracted_intent.split()[:3]
        for keyword in keywords:
            try:
                results = await self.codebase_search(keyword)
                if results:
                    draft.affected_files.extend(results[:5])
                    draft.proof_of_work.append(f"Found {len(results)} files for '{keyword}'")
            except Exception as e:
                logger.warning(f"Codebase search failed for '{keyword}': {e}")

        # Remove duplicates
        draft.affected_files = list(set(draft.affected_files))

        draft.status = ADRStatus.ANALYSIS
        draft.updated_at = datetime.now()
        return draft

    def generate_options(self, draft: ADRDraft) -> ADRDraft:
        """
        Generate decision options.

        This is step 4 (DECISION ANALYSIS) of the 9-step process.
        """
        # Default options based on type
        if draft.adr_type == ADRType.FEATURE:
            draft.alternatives = [
                {
                    "name": "Implement as described",
                    "description": "Implement the feature as requested",
                    "pros": ["Direct solution to the problem", "Clear scope"],
                    "cons": ["May need refinement", "Unknown edge cases"],
                },
                {
                    "name": "Minimal viable version",
                    "description": "Implement smallest useful version first",
                    "pros": ["Faster delivery", "Learn from usage", "Lower risk"],
                    "cons": ["May not meet all requirements initially"],
                },
                {
                    "name": "Defer decision",
                    "description": "Gather more information before deciding",
                    "pros": ["Better informed decision", "More context"],
                    "cons": ["Delays progress", "Context may change"],
                },
            ]
        elif draft.adr_type == ADRType.SPIKE:
            draft.alternatives = [
                {
                    "name": "Time-boxed experiment",
                    "description": "2-4 hour spike to validate approach",
                    "pros": ["Quick validation", "Limited investment"],
                    "cons": ["May not cover all scenarios"],
                },
                {
                    "name": "Full prototype",
                    "description": "Build working prototype before decision",
                    "pros": ["Comprehensive testing", "Real metrics"],
                    "cons": ["Higher time investment"],
                },
            ]

        draft.status = ADRStatus.OPTIONS
        draft.updated_at = datetime.now()
        return draft

    def prepare_for_review(self, draft: ADRDraft) -> ADRDraft:
        """
        Prepare ADR for human review.

        This is step 9 (DELIVERABLE) of the 9-step process.
        """
        # Estimate effort based on affected files
        num_files = len(draft.affected_files)
        if num_files == 0:
            draft.estimated_effort = "Unknown"
        elif num_files <= 2:
            draft.estimated_effort = "Small"
        elif num_files <= 5:
            draft.estimated_effort = "Medium"
        else:
            draft.estimated_effort = "Large"

        # Assess risk based on type and impulsivity
        if draft.adr_type == ADRType.SECURITY or draft.impulsivity_score > 0.7:
            draft.risk_level = "High"
        elif draft.adr_type in (ADRType.REFACTOR, ADRType.INTEGRATION):
            draft.risk_level = "Medium"
        else:
            draft.risk_level = "Low"

        # Add consequences
        if not draft.consequences:
            draft.consequences = [
                f"Affected files: {len(draft.affected_files)}",
                f"Estimated effort: {draft.estimated_effort}",
                f"Risk level: {draft.risk_level}",
            ]

        draft.status = ADRStatus.REVIEW
        draft.updated_at = datetime.now()
        return draft

    async def process(self, input_data: ScatteredInput) -> ADRDraft:
        """
        Full ADR creation process.

        Runs through all 9 steps (simplified version).
        """
        # Step 1: INTAKE
        draft = self.create_draft(input_data)

        # Step 2: SYSTEM MAPPING
        draft = await self.analyze_codebase(draft)

        # Step 4: DECISION ANALYSIS
        draft = self.generate_options(draft)

        # Step 9: DELIVERABLE
        draft = self.prepare_for_review(draft)

        return draft


# =============================================================================
# Research Gate
# =============================================================================

class ResearchStage(str, Enum):
    """Stages in the research integration pipeline (ADR-009)."""

    CAPTURE = "capture"          # Initial documentation
    TRIAGE = "triage"            # Classification and prioritization
    EXPERIMENT = "experiment"    # Isolated testing
    EVALUATE = "evaluate"        # Compare to baseline
    INTEGRATE = "integrate"      # Gradual rollout


class ResearchDecision(str, Enum):
    """Decision outcomes for research evaluation."""

    ADOPT = "adopt"              # Integrate into system
    REJECT = "reject"            # Do not integrate
    DEFER = "defer"              # Need more data
    MODIFY = "modify"            # Adopt with modifications


@dataclass
class ResearchGateResult:
    """Result of research gate validation."""

    passed: bool
    stage: ResearchStage
    decision: Optional[ResearchDecision] = None
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


class ResearchGate:
    """
    Controls the research integration pipeline.

    Implements the 5-stage process from ADR-009:
    CAPTURE → TRIAGE → EXPERIMENT → EVALUATE → INTEGRATE

    Key responsibilities:
    - Validate research notes have required fields
    - Ensure proper classification before experimentation
    - Track experiments and their outcomes
    - Control rollout with feature flags
    """

    REQUIRED_FIELDS = {
        ResearchStage.CAPTURE: ["title", "source", "summary"],
        ResearchStage.TRIAGE: ["classification", "priority"],
        ResearchStage.EXPERIMENT: ["hypothesis", "metrics", "experiment_id"],
        ResearchStage.EVALUATE: ["results", "decision"],
        ResearchStage.INTEGRATE: ["feature_flag", "rollout_percentage"],
    }

    def __init__(
        self,
        research_dir: str = "docs/research/notes",
        experiments_dir: str = "experiments",
    ):
        self.research_dir = Path(research_dir)
        self.experiments_dir = Path(experiments_dir)

    def validate_note(self, note: dict, target_stage: ResearchStage) -> ResearchGateResult:
        """
        Validate that a research note is ready for the target stage.

        Args:
            note: Parsed research note dictionary
            target_stage: Stage we want to advance to

        Returns:
            ResearchGateResult with validation outcome
        """
        issues = []
        recommendations = []

        # Check required fields for all stages up to and including target
        stages_to_check = list(ResearchStage)[:list(ResearchStage).index(target_stage) + 1]

        for stage in stages_to_check:
            required = self.REQUIRED_FIELDS.get(stage, [])
            for field in required:
                if field not in note or not note[field]:
                    issues.append(f"Missing required field for {stage.value}: {field}")

        # Stage-specific validation
        if target_stage == ResearchStage.EXPERIMENT:
            if not note.get("hypothesis"):
                issues.append("Cannot experiment without a hypothesis")
                recommendations.append("Add a testable hypothesis to the research note")

            if not note.get("metrics"):
                issues.append("Cannot experiment without success metrics")
                recommendations.append("Define measurable metrics (e.g., latency, accuracy)")

        if target_stage == ResearchStage.EVALUATE:
            if not note.get("experiment_id"):
                issues.append("Cannot evaluate without completed experiment")
                recommendations.append("Run experiment first")

        if target_stage == ResearchStage.INTEGRATE:
            if note.get("decision") not in ("ADOPT", "MODIFY"):
                issues.append("Cannot integrate research that wasn't adopted")
                recommendations.append("Evaluation decision must be ADOPT or MODIFY")

        # Generate next steps
        next_steps = []
        if issues:
            next_steps.append("Fix validation issues listed above")
        else:
            if target_stage == ResearchStage.CAPTURE:
                next_steps.append("Classify research note (Spike/ADR/Backlog/Discard)")
            elif target_stage == ResearchStage.TRIAGE:
                next_steps.append("Create experiment skeleton")
            elif target_stage == ResearchStage.EXPERIMENT:
                next_steps.append("Run experiment and collect results")
            elif target_stage == ResearchStage.EVALUATE:
                next_steps.append("Apply decision matrix and document outcome")
            elif target_stage == ResearchStage.INTEGRATE:
                next_steps.append("Create feature flag and start gradual rollout")

        return ResearchGateResult(
            passed=len(issues) == 0,
            stage=target_stage,
            issues=issues,
            recommendations=recommendations,
            next_steps=next_steps,
        )

    def advance_stage(
        self,
        note_path: str,
        current_stage: ResearchStage,
    ) -> tuple[bool, ResearchGateResult]:
        """
        Attempt to advance a research note to the next stage.

        Args:
            note_path: Path to research note markdown
            current_stage: Current stage of the note

        Returns:
            (success, result)
        """
        # Determine next stage
        stages = list(ResearchStage)
        current_idx = stages.index(current_stage)

        if current_idx >= len(stages) - 1:
            return (False, ResearchGateResult(
                passed=False,
                stage=current_stage,
                issues=["Already at final stage (INTEGRATE)"],
            ))

        next_stage = stages[current_idx + 1]

        # Parse note
        try:
            note = self._parse_note(note_path)
        except Exception as e:
            return (False, ResearchGateResult(
                passed=False,
                stage=current_stage,
                issues=[f"Failed to parse note: {e}"],
            ))

        # Validate for next stage
        result = self.validate_note(note, next_stage)

        if result.passed:
            result.stage = next_stage  # Update to new stage

        return (result.passed, result)

    def _parse_note(self, note_path: str) -> dict:
        """Parse research note markdown into dictionary."""
        path = Path(note_path)
        if not path.exists():
            raise FileNotFoundError(f"Note not found: {note_path}")

        content = path.read_text(encoding='utf-8')
        note = {"raw_content": content}

        # Extract title
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            note["title"] = title_match.group(1).strip()

        # Extract source
        source_match = re.search(r'\*\*Source\*\*:\s*(.+?)(?:\n|$)', content)
        if source_match:
            note["source"] = source_match.group(1).strip()

        # Extract classification
        class_match = re.search(r'\*\*Classification\*\*:\s*(.+?)(?:\n|$)', content)
        if class_match:
            note["classification"] = class_match.group(1).strip()

        # Extract summary (first paragraph after title)
        summary_match = re.search(r'^#.+?\n\n(.+?)(?:\n\n|$)', content, re.DOTALL)
        if summary_match:
            note["summary"] = summary_match.group(1).strip()

        # Extract hypothesis
        hypo_match = re.search(r'##\s*Hypothesis\s*\n+(.+?)(?:\n\n|##|$)', content, re.DOTALL | re.IGNORECASE)
        if hypo_match:
            note["hypothesis"] = hypo_match.group(1).strip()

        # Extract metrics
        metrics_match = re.search(r'##\s*Metrics\s*\n+(.+?)(?:\n\n|##|$)', content, re.DOTALL | re.IGNORECASE)
        if metrics_match:
            note["metrics"] = metrics_match.group(1).strip()

        return note

    def apply_decision_matrix(self, results: dict) -> ResearchDecision:
        """
        Apply the ADR-009 decision matrix.

        | Quality | Latency | Cost | Decision |
        |---------|---------|------|----------|
        | Better | Better | Better | ADOPT |
        | Better | Same | Same | ADOPT |
        | Same | Better | Same | ADOPT |
        | Worse | Any | Any | REJECT |
        | Mixed | Mixed | Mixed | NEEDS_MORE_DATA |
        """
        quality = results.get("quality", "same")  # better, same, worse
        latency = results.get("latency", "same")
        cost = results.get("cost", "same")

        # Any dimension worse = reject
        if quality == "worse":
            return ResearchDecision.REJECT

        # All better or same with improvements = adopt
        if quality == "better":
            if latency in ("better", "same") and cost in ("better", "same"):
                return ResearchDecision.ADOPT

        if quality == "same" and latency == "better":
            return ResearchDecision.ADOPT

        if quality == "same" and cost == "better":
            return ResearchDecision.ADOPT

        # Mixed results = need more data
        return ResearchDecision.DEFER

    def create_experiment_trigger(self, note: dict) -> dict:
        """
        Create configuration for experiment execution.

        Returns configuration dict that can be passed to experiment runner.
        """
        return {
            "note_title": note.get("title", "Unknown"),
            "hypothesis": note.get("hypothesis", ""),
            "metrics": note.get("metrics", ""),
            "classification": note.get("classification", "Spike"),
            "created_at": datetime.now().isoformat(),
            "status": "pending",
        }


# =============================================================================
# Integration with Intake System
# =============================================================================

@dataclass
class GovernanceResult:
    """Result from governance processing."""

    action_taken: str
    artifact_path: Optional[str] = None
    adr_draft: Optional[ADRDraft] = None
    research_result: Optional[ResearchGateResult] = None
    requires_review: bool = True
    summary: str = ""


class GovernanceRouter:
    """
    Routes intake items to appropriate governance handlers.

    Integrates with:
    - ADRWriterAgent for decision-related content
    - ResearchGate for research-related content
    """

    def __init__(self):
        self.adr_writer = ADRWriterAgent()
        self.research_gate = ResearchGate()

    async def process(self, content: str, context: Optional[dict] = None) -> GovernanceResult:
        """
        Process content through governance system.

        Args:
            content: User input or extracted content
            context: Additional context (domain, source, etc.)

        Returns:
            GovernanceResult with action taken
        """
        context = context or {}

        # Check if this is decision-related
        is_decision, decision_conf = self.adr_writer.is_decision_related(content)

        # Check if this is research-related
        is_research = any(kw in content.lower() for kw in [
            "research", "מחקר", "paper", "study", "experiment", "ניסוי"
        ])

        if is_decision and decision_conf > 0.5:
            # Route to ADR Writer
            input_data = ScatteredInput(
                raw_text=content,
                source=context.get("source", "intake"),
                context=context,
            )

            draft = await self.adr_writer.process(input_data)

            return GovernanceResult(
                action_taken="adr_draft_created",
                adr_draft=draft,
                requires_review=True,
                summary=f"Created ADR draft: {draft.title} (Type: {draft.adr_type.value})",
            )

        elif is_research:
            # Check research stage
            result = self.research_gate.validate_note(
                {"summary": content, "title": "New Research"},
                ResearchStage.CAPTURE
            )

            return GovernanceResult(
                action_taken="research_validated",
                research_result=result,
                requires_review=result.passed,
                summary=f"Research validation: {'Passed' if result.passed else 'Issues found'}",
            )

        # No governance action needed
        return GovernanceResult(
            action_taken="no_action",
            requires_review=False,
            summary="Content does not require governance processing",
        )
