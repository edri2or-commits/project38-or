"""
WAT Framework Self-Healing Executor

Execution engine with automatic error recovery and the Loop pattern.
"""

import asyncio
import logging
import re
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import uuid4

from src.wat.types import (
    ErrorRecoveryStrategy,
    ErrorType,
    ExecutionResult,
    ExecutionStatus,
    RecoveryAction,
    StepResult,
    ToolDefinition,
    WorkflowDefinition,
    WorkflowStep,
)
from src.wat.registry import ToolRegistry
from src.wat.workflow import Workflow
from src.wat.agent import AgentDefinition

logger = logging.getLogger(__name__)


@dataclass
class ExecutionContext:
    """
    Context for workflow execution.

    Maintains state across steps and provides access to results.
    """

    workflow: WorkflowDefinition
    agent: AgentDefinition
    inputs: Dict[str, Any] = field(default_factory=dict)
    # Step results indexed by step ID
    step_results: Dict[str, StepResult] = field(default_factory=dict)
    # Variables that can be referenced across steps
    variables: Dict[str, Any] = field(default_factory=dict)
    # Trace ID for observability
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    # Start time
    started_at: datetime = field(default_factory=datetime.utcnow)
    # Total cost accumulated
    total_cost_usd: float = 0.0
    # Total tokens used
    total_tokens: int = 0

    def get_reference(self, ref: str) -> Any:
        """
        Resolve a reference like $prev.field or $step_id.field.

        Args:
            ref: Reference string (e.g., "$prev.output", "$search.results")

        Returns:
            Referenced value or None
        """
        if not ref.startswith("$"):
            return ref

        parts = ref.lstrip("$").split(".", 1)
        source = parts[0]
        field_path = parts[1] if len(parts) > 1 else None

        # Get source value
        if source == "prev":
            # Get last step result
            if self.step_results:
                last_result = list(self.step_results.values())[-1]
                value = last_result.output
            else:
                return None
        elif source == "inputs":
            value = self.inputs
        elif source in self.step_results:
            value = self.step_results[source].output
        elif source in self.variables:
            value = self.variables[source]
        else:
            return None

        # Navigate field path
        if field_path:
            for part in field_path.split("."):
                if isinstance(value, dict):
                    value = value.get(part)
                elif hasattr(value, part):
                    value = getattr(value, part)
                else:
                    return None

        return value

    def resolve_inputs(self, step: WorkflowStep) -> Dict[str, Any]:
        """
        Resolve all inputs for a step.

        Args:
            step: Workflow step

        Returns:
            Resolved input dictionary
        """
        resolved = {}

        # Start with static inputs
        for key, value in step.inputs.items():
            if isinstance(value, str) and value.startswith("$"):
                resolved[key] = self.get_reference(value)
            else:
                resolved[key] = value

        # Apply input mappings
        for key, ref in step.input_mappings.items():
            resolved[key] = self.get_reference(ref)

        return resolved


class ErrorClassifier:
    """
    Classifies errors into ErrorType categories for recovery matching.
    """

    # Patterns for error classification
    PATTERNS = {
        ErrorType.NETWORK: [
            r"connection.*(?:refused|reset|timeout)",
            r"network.*(?:unreachable|error)",
            r"socket.*(?:timeout|error)",
            r"ssl.*(?:error|certificate)",
            r"dns.*(?:lookup|resolution)",
        ],
        ErrorType.AUTHENTICATION: [
            r"401.*unauthorized",
            r"403.*forbidden",
            r"authentication.*(?:failed|error)",
            r"invalid.*(?:token|credential|api.?key)",
            r"access.*denied",
        ],
        ErrorType.RATE_LIMIT: [
            r"429.*too.?many.?requests",
            r"rate.*limit.*(?:exceeded|reached)",
            r"quota.*exceeded",
            r"throttl",
        ],
        ErrorType.VALIDATION: [
            r"validation.*(?:error|failed)",
            r"invalid.*(?:input|parameter|argument)",
            r"missing.*(?:required|field)",
            r"type.*error",
        ],
        ErrorType.DEPENDENCY: [
            r"module.*not.*found",
            r"import.*error",
            r"no.*module.*named",
            r"package.*not.*(?:found|installed)",
        ],
        ErrorType.RESOURCE: [
            r"404.*not.*found",
            r"resource.*not.*(?:found|exist)",
            r"no.*such.*(?:file|directory)",
            r"file.*not.*found",
        ],
        ErrorType.PERMISSION: [
            r"permission.*denied",
            r"access.*denied",
            r"insufficient.*(?:permissions|privileges)",
            r"operation.*not.*permitted",
        ],
        ErrorType.SYNTAX: [
            r"syntax.*error",
            r"parse.*error",
            r"unexpected.*(?:token|character)",
            r"invalid.*syntax",
        ],
        ErrorType.TIMEOUT: [
            r"timeout.*(?:expired|exceeded)",
            r"operation.*timed.*out",
            r"deadline.*exceeded",
        ],
    }

    @classmethod
    def classify(cls, error: Exception) -> ErrorType:
        """
        Classify an exception into an ErrorType.

        Args:
            error: Exception to classify

        Returns:
            Matching ErrorType
        """
        error_str = str(error).lower()
        error_type_str = type(error).__name__.lower()
        combined = f"{error_type_str}: {error_str}"

        for error_type, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, combined, re.IGNORECASE):
                    return error_type

        return ErrorType.UNKNOWN


class SelfHealingExecutor:
    """
    Self-healing workflow executor with the Loop pattern.

    The Loop Pattern:
    1. Execute tool
    2. If error, analyze stderr/exception
    3. Match to recovery strategy
    4. Apply recovery action
    5. Retry (up to max_retries)
    6. If still failing, escalate

    Provides:
    - Automatic error classification
    - Strategy-based recovery
    - Dependency installation
    - Backoff and retry
    - Fallback execution
    - Cost tracking
    """

    def __init__(
        self,
        registry: ToolRegistry,
        max_retries: int = 3,
        default_timeout_seconds: int = 60,
        cost_budget_usd: Optional[float] = None,
    ) -> None:
        """
        Initialize executor.

        Args:
            registry: Tool registry
            max_retries: Default max retries per step
            default_timeout_seconds: Default timeout per step
            cost_budget_usd: Optional cost budget
        """
        self._registry = registry
        self._max_retries = max_retries
        self._default_timeout = default_timeout_seconds
        self._cost_budget = cost_budget_usd
        self._error_classifier = ErrorClassifier()

        # Default recovery strategies
        self._default_strategies: List[ErrorRecoveryStrategy] = [
            ErrorRecoveryStrategy(
                error_type=ErrorType.NETWORK,
                action=RecoveryAction.RETRY_WITH_BACKOFF,
                max_attempts=3,
                backoff_seconds=2.0,
                backoff_multiplier=2.0,
            ),
            ErrorRecoveryStrategy(
                error_type=ErrorType.RATE_LIMIT,
                action=RecoveryAction.RETRY_WITH_BACKOFF,
                max_attempts=5,
                backoff_seconds=5.0,
                backoff_multiplier=2.0,
            ),
            ErrorRecoveryStrategy(
                error_type=ErrorType.DEPENDENCY,
                action=RecoveryAction.INSTALL_DEPENDENCY,
                max_attempts=1,
            ),
            ErrorRecoveryStrategy(
                error_type=ErrorType.AUTHENTICATION,
                action=RecoveryAction.REFRESH_AUTH,
                max_attempts=1,
            ),
            ErrorRecoveryStrategy(
                error_type=ErrorType.TIMEOUT,
                action=RecoveryAction.INCREASE_TIMEOUT,
                max_attempts=2,
            ),
        ]

    async def run(
        self,
        workflow: Workflow,
        agent: AgentDefinition,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Execute a workflow with self-healing.

        Args:
            workflow: Workflow to execute
            agent: Agent executing the workflow
            inputs: Input values for the workflow

        Returns:
            ExecutionResult with all step results
        """
        context = ExecutionContext(
            workflow=workflow.definition,
            agent=agent,
            inputs=inputs or {},
        )

        logger.info(
            f"Starting workflow: {workflow.name} (trace: {context.trace_id})"
        )

        result = ExecutionResult(
            workflow_name=workflow.name,
            status=ExecutionStatus.IN_PROGRESS,
            trace_id=context.trace_id,
            started_at=context.started_at,
        )

        try:
            for step in workflow.definition.steps:
                # Check condition
                if step.condition:
                    condition_result = self._evaluate_condition(step.condition, context)
                    if not condition_result:
                        logger.debug(f"Skipping step {step.id}: condition not met")
                        continue

                # Execute step with recovery
                step_result = await self._execute_step_with_recovery(
                    step, context, workflow.definition.error_handlers
                )

                context.step_results[step.id] = step_result
                result.step_results.append(step_result)
                context.total_cost_usd += step_result.cost_usd
                context.total_tokens += step_result.tokens_used

                # Check budget
                if self._cost_budget and context.total_cost_usd > self._cost_budget:
                    raise RuntimeError(
                        f"Cost budget exceeded: ${context.total_cost_usd:.4f} > ${self._cost_budget:.4f}"
                    )

                # Check step failure
                if step_result.status == ExecutionStatus.FAILED:
                    on_error = step.on_error or "abort"
                    if on_error == "abort":
                        result.status = ExecutionStatus.FAILED
                        result.error = f"Step {step.id} failed: {step_result.error}"
                        break
                    elif on_error == "skip":
                        logger.warning(f"Skipping failed step {step.id}")
                        continue

            # Workflow completed
            if result.status == ExecutionStatus.IN_PROGRESS:
                result.status = ExecutionStatus.SUCCESS
                # Get final output from last step
                if result.step_results:
                    result.output = result.step_results[-1].output

        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error = str(e)
            logger.error(f"Workflow failed: {e}\n{traceback.format_exc()}")

        # Finalize result
        result.completed_at = datetime.utcnow()
        result.total_duration_ms = (
            result.completed_at - result.started_at
        ).total_seconds() * 1000
        result.total_cost_usd = context.total_cost_usd
        result.total_tokens = context.total_tokens
        result.total_retries = sum(sr.retries for sr in result.step_results)

        logger.info(
            f"Workflow {workflow.name} completed: {result.status.value} "
            f"(duration: {result.total_duration_ms:.0f}ms, "
            f"cost: ${result.total_cost_usd:.4f})"
        )

        return result

    async def _execute_step_with_recovery(
        self,
        step: WorkflowStep,
        context: ExecutionContext,
        error_handlers: List[ErrorRecoveryStrategy],
    ) -> StepResult:
        """
        Execute a step with automatic error recovery.

        This is the core "Loop" pattern implementation.
        """
        tool = self._registry.get(step.tool)
        if not tool:
            return StepResult(
                step_id=step.id,
                tool_name=step.tool,
                status=ExecutionStatus.FAILED,
                error=f"Tool not found: {step.tool}",
            )

        # Combine error handlers
        strategies = error_handlers + self._default_strategies

        # Resolve inputs
        resolved_inputs = context.resolve_inputs(step)

        max_retries = step.max_retries or self._max_retries
        timeout = step.timeout_seconds or self._default_timeout
        attempts = 0
        last_error: Optional[Exception] = None
        last_error_type: Optional[ErrorType] = None

        while attempts <= max_retries:
            attempts += 1
            start_time = time.time()

            try:
                # Execute the tool
                output = await self._execute_tool(tool, resolved_inputs, timeout)

                duration_ms = (time.time() - start_time) * 1000
                return StepResult(
                    step_id=step.id,
                    tool_name=step.tool,
                    status=ExecutionStatus.SUCCESS,
                    output=output,
                    duration_ms=duration_ms,
                    retries=attempts - 1,
                )

            except Exception as e:
                last_error = e
                last_error_type = ErrorClassifier.classify(e)
                duration_ms = (time.time() - start_time) * 1000

                logger.warning(
                    f"Step {step.id} attempt {attempts} failed: "
                    f"[{last_error_type.value}] {e}"
                )

                # Find matching recovery strategy
                strategy = self._find_strategy(last_error_type, strategies)

                if strategy and attempts <= strategy.max_attempts:
                    # Apply recovery action
                    recovery_result = await self._apply_recovery(
                        strategy, last_error, tool, resolved_inputs, context
                    )

                    if recovery_result.get("should_retry", True):
                        # Apply backoff if needed
                        if strategy.action == RecoveryAction.RETRY_WITH_BACKOFF:
                            wait_time = strategy.backoff_seconds * (
                                strategy.backoff_multiplier ** (attempts - 1)
                            )
                            logger.debug(f"Backing off for {wait_time:.1f}s")
                            await asyncio.sleep(wait_time)

                        # Update timeout if increased
                        if "new_timeout" in recovery_result:
                            timeout = recovery_result["new_timeout"]

                        continue  # Retry

                # No recovery possible, fail
                break

        # All retries exhausted
        return StepResult(
            step_id=step.id,
            tool_name=step.tool,
            status=ExecutionStatus.FAILED,
            error=str(last_error),
            error_type=last_error_type,
            duration_ms=(time.time() - start_time) * 1000,
            retries=attempts - 1,
        )

    async def _execute_tool(
        self,
        tool: ToolDefinition,
        inputs: Dict[str, Any],
        timeout: int,
    ) -> Any:
        """Execute a tool with timeout."""
        if not tool.handler:
            raise RuntimeError(f"Tool {tool.name} has no handler")

        if tool.is_async:
            return await asyncio.wait_for(
                tool.handler(**inputs),
                timeout=timeout,
            )
        else:
            # Run sync function in executor
            loop = asyncio.get_event_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(None, lambda: tool.handler(**inputs)),
                timeout=timeout,
            )

    def _find_strategy(
        self,
        error_type: ErrorType,
        strategies: List[ErrorRecoveryStrategy],
    ) -> Optional[ErrorRecoveryStrategy]:
        """Find a matching recovery strategy for an error type."""
        for strategy in strategies:
            if strategy.error_type == error_type:
                return strategy
        return None

    async def _apply_recovery(
        self,
        strategy: ErrorRecoveryStrategy,
        error: Exception,
        tool: ToolDefinition,
        inputs: Dict[str, Any],
        context: ExecutionContext,
    ) -> Dict[str, Any]:
        """
        Apply a recovery action.

        Returns dict with recovery results and whether to retry.
        """
        result: Dict[str, Any] = {"should_retry": True}

        if strategy.action == RecoveryAction.RETRY:
            logger.debug("Recovery: simple retry")

        elif strategy.action == RecoveryAction.RETRY_WITH_BACKOFF:
            logger.debug("Recovery: retry with backoff")

        elif strategy.action == RecoveryAction.INSTALL_DEPENDENCY:
            # Extract missing module name from error
            match = re.search(r"No module named ['\"]?(\w+)['\"]?", str(error))
            if match:
                module_name = match.group(1)
                logger.info(f"Recovery: installing missing dependency: {module_name}")
                try:
                    import subprocess
                    subprocess.run(
                        ["pip", "install", module_name],
                        check=True,
                        capture_output=True,
                    )
                    logger.info(f"Successfully installed: {module_name}")
                except Exception as e:
                    logger.error(f"Failed to install {module_name}: {e}")
                    result["should_retry"] = False

        elif strategy.action == RecoveryAction.REFRESH_AUTH:
            logger.info("Recovery: refreshing authentication")
            # This would trigger auth refresh logic
            # For now, just retry and hope the token was refreshed elsewhere
            await asyncio.sleep(1)

        elif strategy.action == RecoveryAction.INCREASE_TIMEOUT:
            new_timeout = tool.timeout_seconds + 30
            logger.info(f"Recovery: increasing timeout to {new_timeout}s")
            result["new_timeout"] = new_timeout

        elif strategy.action == RecoveryAction.FALLBACK:
            if strategy.fallback_tool:
                logger.info(f"Recovery: falling back to {strategy.fallback_tool}")
                # The caller should handle this by switching tools
                result["fallback_tool"] = strategy.fallback_tool

        elif strategy.action == RecoveryAction.ALERT:
            logger.warning(
                f"Recovery: alerting (severity: {strategy.alert_severity})"
            )
            # Would send alert through notification system

        elif strategy.action == RecoveryAction.ESCALATE:
            logger.error("Recovery: escalating to human")
            result["should_retry"] = False

        elif strategy.action == RecoveryAction.SKIP:
            logger.warning("Recovery: skipping step")
            result["should_retry"] = False

        elif strategy.action == RecoveryAction.ABORT:
            logger.error("Recovery: aborting workflow")
            result["should_retry"] = False

        return result

    def _evaluate_condition(
        self,
        condition: str,
        context: ExecutionContext,
    ) -> bool:
        """
        Evaluate a step condition.

        Supports simple expressions like:
        - "$prev.status == 'success'"
        - "$inputs.should_enrich == true"
        """
        try:
            # Replace references with actual values
            def replace_ref(match: re.Match) -> str:
                ref = match.group(0)
                value = context.get_reference(ref)
                if value is None:
                    return "None"
                elif isinstance(value, str):
                    return f"'{value}'"
                elif isinstance(value, bool):
                    return str(value)
                else:
                    return str(value)

            resolved = re.sub(r"\$[\w.]+", replace_ref, condition)

            # Evaluate safely
            # Only allow simple comparisons
            allowed_names = {"True": True, "False": False, "None": None}
            result = eval(resolved, {"__builtins__": {}}, allowed_names)
            return bool(result)

        except Exception as e:
            logger.warning(f"Failed to evaluate condition '{condition}': {e}")
            return False
