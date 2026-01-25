"""
WAT Framework Workflow Engine

Workflow definition, parsing, and execution engine.
Supports YAML-based workflow definitions and natural language goals.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from src.wat.types import (
    ErrorRecoveryStrategy,
    ErrorType,
    RecoveryAction,
    ToolInput,
    ToolOutput,
    WorkflowDefinition,
    WorkflowStep,
)

logger = logging.getLogger(__name__)


class Workflow:
    """
    Workflow wrapper with parsing and validation.

    Workflows can be created from:
    - YAML files
    - Python dictionaries
    - Natural language descriptions (requires LLM)
    """

    def __init__(self, definition: WorkflowDefinition) -> None:
        """
        Initialize workflow with a definition.

        Args:
            definition: WorkflowDefinition object
        """
        self.definition = definition
        self._validated = False

    @property
    def name(self) -> str:
        """Get workflow name."""
        return self.definition.name

    @property
    def steps(self) -> List[WorkflowStep]:
        """Get workflow steps."""
        return self.definition.steps

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "Workflow":
        """
        Load workflow from YAML file.

        Args:
            path: Path to YAML file

        Returns:
            Workflow instance

        Example YAML:
            name: lead-gen-dentist
            description: Generate leads for dental practices
            version: "1.0.0"
            inputs:
              location:
                type: str
                description: Target location
                required: true
              niche:
                type: str
                description: Business niche
                default: "Dentist"
            steps:
              - id: search
                tool: search_places
                description: Search for businesses
                inputs:
                  query: "$inputs.niche"
                  location: "$inputs.location"
              - id: enrich
                tool: get_place_details
                description: Get contact details
                input_mappings:
                  place_id: "$prev.place_id"
            constraints:
              - "Do not hallucinate contact info"
              - "Respect robots.txt"
            error_handlers:
              - error_type: rate_limit
                action: retry_with_backoff
                max_attempts: 5
                backoff_seconds: 2.0
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {path}")

        with open(path, "r") as f:
            data = yaml.safe_load(f)

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Workflow":
        """
        Create workflow from dictionary.

        Args:
            data: Workflow definition dictionary

        Returns:
            Workflow instance
        """
        # Parse inputs
        inputs = {}
        for name, input_data in data.get("inputs", {}).items():
            if isinstance(input_data, dict):
                inputs[name] = ToolInput(
                    name=name,
                    type=input_data.get("type", "str"),
                    description=input_data.get("description", f"Input: {name}"),
                    required=input_data.get("required", True),
                    default=input_data.get("default"),
                )
            else:
                # Simple type annotation
                inputs[name] = ToolInput(
                    name=name,
                    type=str(input_data),
                    description=f"Input: {name}",
                    required=True,
                )

        # Parse steps
        steps = []
        for step_data in data.get("steps", []):
            steps.append(
                WorkflowStep(
                    id=step_data.get("id", f"step_{len(steps)}"),
                    tool=step_data["tool"],
                    description=step_data.get("description", ""),
                    inputs=step_data.get("inputs", {}),
                    input_mappings=step_data.get("input_mappings", {}),
                    condition=step_data.get("condition"),
                    on_error=step_data.get("on_error"),
                    max_retries=step_data.get("max_retries", 3),
                    timeout_seconds=step_data.get("timeout_seconds", 60),
                )
            )

        # Parse error handlers
        error_handlers = []
        for handler_data in data.get("error_handlers", []):
            error_handlers.append(
                ErrorRecoveryStrategy(
                    error_type=ErrorType(handler_data.get("error_type", "unknown")),
                    action=RecoveryAction(handler_data.get("action", "retry")),
                    max_attempts=handler_data.get("max_attempts", 3),
                    backoff_seconds=handler_data.get("backoff_seconds", 1.0),
                    backoff_multiplier=handler_data.get("backoff_multiplier", 2.0),
                    fallback_tool=handler_data.get("fallback_tool"),
                    alert_severity=handler_data.get("alert_severity"),
                )
            )

        # Parse outputs
        outputs = None
        if "outputs" in data:
            outputs = ToolOutput(
                type=data["outputs"].get("type", "Any"),
                description=data["outputs"].get("description", "Workflow output"),
                schema=data["outputs"].get("schema"),
            )

        definition = WorkflowDefinition(
            name=data.get("name", "unnamed-workflow"),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            steps=steps,
            constraints=data.get("constraints", []),
            required_tools=[step.tool for step in steps],
            error_handlers=error_handlers,
            timeout_seconds=data.get("timeout_seconds", 300),
            cost_budget_usd=data.get("cost_budget_usd"),
            tags=data.get("tags", []),
            inputs=inputs,
            outputs=outputs,
        )

        return cls(definition)

    @classmethod
    def from_markdown(cls, path: Union[str, Path]) -> "Workflow":
        """
        Load workflow from Markdown file (natural language format).

        Args:
            path: Path to Markdown file

        Returns:
            Workflow instance

        Example Markdown:
            # Workflow: Dentist Lead Generation

            ## Objective
            Identify, verify, and extract contact details for 50 dental practices.

            ## Inputs
            - Location: "San Francisco, CA"
            - Niche: "Dentist"

            ## Process Steps
            1. **Discovery**: Use the google_maps tool to search for entities.
            2. **Filter**: Exclude chains; prioritize private practices.
            3. **Enrichment**: Visit website to find contact email.
            4. **Validation**: Verify email format.
            5. **Output**: Save to data/output/sf_dentists.csv

            ## Constraints
            - Do not hallucinate contact info
            - Respect robots.txt
            - Pause for 2 seconds between browser requests
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {path}")

        content = path.read_text()
        return cls._parse_markdown(content, path.stem)

    @classmethod
    def _parse_markdown(cls, content: str, default_name: str = "workflow") -> "Workflow":
        """Parse markdown content into workflow definition."""
        lines = content.split("\n")

        name = default_name
        description = ""
        inputs: Dict[str, ToolInput] = {}
        steps: List[WorkflowStep] = []
        constraints: List[str] = []

        current_section = None
        step_counter = 0

        for line in lines:
            line = line.strip()

            # Parse section headers
            if line.startswith("# Workflow:") or line.startswith("# "):
                name = line.lstrip("# ").replace("Workflow:", "").strip()
                name = re.sub(r"[^a-zA-Z0-9-]", "-", name.lower())
                continue

            if line.startswith("## "):
                section = line.lstrip("## ").lower()
                if "objective" in section or "description" in section:
                    current_section = "description"
                elif "input" in section:
                    current_section = "inputs"
                elif "step" in section or "process" in section:
                    current_section = "steps"
                elif "constraint" in section:
                    current_section = "constraints"
                else:
                    current_section = None
                continue

            # Parse content based on section
            if not line:
                continue

            if current_section == "description":
                description += line + " "

            elif current_section == "inputs":
                # Parse "- Location: value" or "- Location (type): value"
                if line.startswith("-"):
                    match = re.match(r"-\s*(\w+)(?:\s*\((\w+)\))?:\s*(.+)", line)
                    if match:
                        input_name = match.group(1).lower()
                        input_type = match.group(2) or "str"
                        input_value = match.group(3).strip('"\'')
                        inputs[input_name] = ToolInput(
                            name=input_name,
                            type=input_type,
                            description=f"Input: {input_name}",
                            required=False,
                            default=input_value,
                        )

            elif current_section == "steps":
                # Parse numbered or bulleted steps
                step_match = re.match(r"(?:\d+\.|[-*])\s*\**(\w+)\**:\s*(.+)", line)
                if step_match:
                    step_name = step_match.group(1).lower()
                    step_desc = step_match.group(2)

                    # Try to extract tool name from description
                    tool_match = re.search(r"(?:use|call|invoke)\s+(?:the\s+)?(\w+)\s+tool", step_desc, re.I)
                    tool_name = tool_match.group(1) if tool_match else step_name

                    steps.append(
                        WorkflowStep(
                            id=f"step_{step_counter}",
                            tool=tool_name,
                            description=step_desc,
                        )
                    )
                    step_counter += 1

            elif current_section == "constraints":
                if line.startswith("-"):
                    constraints.append(line.lstrip("- "))

        definition = WorkflowDefinition(
            name=name,
            description=description.strip(),
            steps=steps,
            constraints=constraints,
            required_tools=[step.tool for step in steps],
            inputs=inputs,
        )

        return cls(definition)

    def validate(self, available_tools: List[str]) -> List[str]:
        """
        Validate workflow against available tools.

        Args:
            available_tools: List of available tool names

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check required tools
        for tool_name in self.definition.required_tools:
            if tool_name not in available_tools:
                errors.append(f"Required tool not found: {tool_name}")

        # Check step references
        step_ids = {step.id for step in self.definition.steps}
        for step in self.definition.steps:
            for key, mapping in step.input_mappings.items():
                if mapping.startswith("$"):
                    ref = mapping.split(".")[0].lstrip("$")
                    if ref not in ("prev", "inputs") and ref not in step_ids:
                        errors.append(f"Step {step.id}: Invalid reference '{mapping}'")

        # Check for circular dependencies (simple check)
        seen_ids = set()
        for step in self.definition.steps:
            if step.id in seen_ids:
                errors.append(f"Duplicate step ID: {step.id}")
            seen_ids.add(step.id)

        self._validated = len(errors) == 0
        return errors

    def to_prompt(self) -> str:
        """
        Convert workflow to natural language prompt for LLM execution.

        Returns:
            Prompt string
        """
        prompt_parts = [
            f"# Workflow: {self.definition.name}",
            "",
            f"## Objective",
            self.definition.description,
            "",
        ]

        if self.definition.inputs:
            prompt_parts.append("## Inputs")
            for name, input_def in self.definition.inputs.items():
                default = f" (default: {input_def.default})" if input_def.default else ""
                prompt_parts.append(f"- {name}: {input_def.description}{default}")
            prompt_parts.append("")

        prompt_parts.append("## Steps")
        for i, step in enumerate(self.definition.steps, 1):
            prompt_parts.append(f"{i}. **{step.id}**: {step.description}")
            prompt_parts.append(f"   - Tool: `{step.tool}`")
            if step.inputs:
                prompt_parts.append(f"   - Inputs: {step.inputs}")
            if step.condition:
                prompt_parts.append(f"   - Condition: {step.condition}")
        prompt_parts.append("")

        if self.definition.constraints:
            prompt_parts.append("## Constraints")
            for constraint in self.definition.constraints:
                prompt_parts.append(f"- {constraint}")
            prompt_parts.append("")

        return "\n".join(prompt_parts)

    def to_yaml(self) -> str:
        """Export workflow to YAML string."""
        return self.definition.to_yaml()

    def to_dict(self) -> Dict[str, Any]:
        """Export workflow to dictionary."""
        return self.definition.to_dict()


class WorkflowEngine:
    """
    Engine for managing and executing workflows.

    Provides:
    - Workflow loading and caching
    - Workflow validation
    - Workflow composition
    """

    def __init__(self, workflows_dir: Optional[Union[str, Path]] = None) -> None:
        """
        Initialize workflow engine.

        Args:
            workflows_dir: Optional directory for workflow files
        """
        self._workflows: Dict[str, Workflow] = {}
        self._workflows_dir = Path(workflows_dir) if workflows_dir else None

    def load(self, name: str) -> Optional[Workflow]:
        """
        Load a workflow by name.

        First checks cache, then filesystem.

        Args:
            name: Workflow name

        Returns:
            Workflow instance or None
        """
        if name in self._workflows:
            return self._workflows[name]

        if self._workflows_dir:
            # Try YAML first
            yaml_path = self._workflows_dir / f"{name}.yaml"
            if yaml_path.exists():
                workflow = Workflow.from_yaml(yaml_path)
                self._workflows[name] = workflow
                return workflow

            # Try Markdown
            md_path = self._workflows_dir / f"{name}.md"
            if md_path.exists():
                workflow = Workflow.from_markdown(md_path)
                self._workflows[name] = workflow
                return workflow

        return None

    def register(self, workflow: Workflow) -> None:
        """
        Register a workflow in the engine.

        Args:
            workflow: Workflow to register
        """
        self._workflows[workflow.name] = workflow
        logger.debug(f"Registered workflow: {workflow.name}")

    def list(self) -> List[str]:
        """List all registered workflow names."""
        return list(self._workflows.keys())

    def get(self, name: str) -> Optional[Workflow]:
        """Get a workflow by name."""
        return self._workflows.get(name)

    def discover(self) -> int:
        """
        Discover workflows from the workflows directory.

        Returns:
            Number of workflows discovered
        """
        if not self._workflows_dir or not self._workflows_dir.exists():
            return 0

        count = 0
        for file_path in self._workflows_dir.iterdir():
            if file_path.suffix in (".yaml", ".yml"):
                try:
                    workflow = Workflow.from_yaml(file_path)
                    self._workflows[workflow.name] = workflow
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to load workflow {file_path}: {e}")
            elif file_path.suffix == ".md":
                try:
                    workflow = Workflow.from_markdown(file_path)
                    self._workflows[workflow.name] = workflow
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to load workflow {file_path}: {e}")

        logger.info(f"Discovered {count} workflows from {self._workflows_dir}")
        return count

    def compose(
        self,
        name: str,
        workflows: List[str],
        description: str = "",
    ) -> Workflow:
        """
        Compose multiple workflows into a single workflow.

        Args:
            name: Name for the composed workflow
            workflows: List of workflow names to compose
            description: Description for the composed workflow

        Returns:
            New composed Workflow
        """
        all_steps: List[WorkflowStep] = []
        all_constraints: List[str] = []
        all_inputs: Dict[str, ToolInput] = {}
        all_error_handlers: List[ErrorRecoveryStrategy] = []

        for wf_name in workflows:
            workflow = self.get(wf_name)
            if not workflow:
                raise ValueError(f"Workflow not found: {wf_name}")

            # Prefix step IDs to avoid conflicts
            for step in workflow.definition.steps:
                prefixed_step = WorkflowStep(
                    id=f"{wf_name}_{step.id}",
                    tool=step.tool,
                    description=f"[{wf_name}] {step.description}",
                    inputs=step.inputs,
                    input_mappings=step.input_mappings,
                    condition=step.condition,
                    on_error=step.on_error,
                    max_retries=step.max_retries,
                    timeout_seconds=step.timeout_seconds,
                )
                all_steps.append(prefixed_step)

            all_constraints.extend(workflow.definition.constraints)
            all_inputs.update(workflow.definition.inputs)
            all_error_handlers.extend(workflow.definition.error_handlers)

        definition = WorkflowDefinition(
            name=name,
            description=description or f"Composed workflow: {', '.join(workflows)}",
            steps=all_steps,
            constraints=list(set(all_constraints)),
            required_tools=list({step.tool for step in all_steps}),
            error_handlers=all_error_handlers,
            inputs=all_inputs,
        )

        return Workflow(definition)
