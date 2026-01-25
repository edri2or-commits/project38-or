"""
WAT Framework Type Definitions

Core data structures for the Workflows, Agents, Tools framework.
Uses dataclasses for type safety and serialization support.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union
import json


class ToolCategory(str, Enum):
    """Categories for tool classification and discovery."""

    DATA = "data"  # Data retrieval and processing
    COMMUNICATION = "communication"  # Email, notifications, messaging
    DEPLOYMENT = "deployment"  # Railway, cloud deployments
    MONITORING = "monitoring"  # Health checks, metrics
    STORAGE = "storage"  # File systems, databases, cloud storage
    INTEGRATION = "integration"  # GitHub, n8n, external APIs
    WORKSPACE = "workspace"  # Google Workspace tools
    SECURITY = "security"  # Secret management, authentication
    BROWSER = "browser"  # Web scraping, automation
    GENERAL = "general"  # Uncategorized tools


class ExecutionStatus(str, Enum):
    """Status of a workflow or tool execution."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    RECOVERED = "recovered"
    CANCELLED = "cancelled"


class ErrorType(str, Enum):
    """Types of errors for recovery strategy matching."""

    NETWORK = "network"  # Connection errors, timeouts
    AUTHENTICATION = "authentication"  # Auth failures
    RATE_LIMIT = "rate_limit"  # API throttling
    VALIDATION = "validation"  # Input/output validation
    DEPENDENCY = "dependency"  # Missing dependencies
    RESOURCE = "resource"  # Resource not found
    PERMISSION = "permission"  # Access denied
    SYNTAX = "syntax"  # Code/config syntax errors
    TIMEOUT = "timeout"  # Operation timeout
    UNKNOWN = "unknown"  # Unclassified errors


class RecoveryAction(str, Enum):
    """Actions for error recovery."""

    RETRY = "retry"
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    FALLBACK = "fallback"
    INSTALL_DEPENDENCY = "install_dependency"
    REFRESH_AUTH = "refresh_auth"
    INCREASE_TIMEOUT = "increase_timeout"
    ALERT = "alert"
    ESCALATE = "escalate"
    SKIP = "skip"
    ABORT = "abort"


@dataclass
class ToolInput:
    """Definition of a tool input parameter."""

    name: str
    type: str  # Python type annotation as string
    description: str
    required: bool = True
    default: Any = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "required": self.required,
            "default": self.default,
        }


@dataclass
class ToolOutput:
    """Definition of a tool output."""

    type: str  # Python type annotation as string
    description: str
    schema: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type,
            "description": self.description,
            "schema": self.schema,
        }


@dataclass
class CostEstimate:
    """Cost estimate for tool execution."""

    model: str  # e.g., "claude-3-5-sonnet"
    input_tokens_estimate: int = 0
    output_tokens_estimate: int = 0
    api_calls: int = 1
    estimated_cost_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "model": self.model,
            "input_tokens_estimate": self.input_tokens_estimate,
            "output_tokens_estimate": self.output_tokens_estimate,
            "api_calls": self.api_calls,
            "estimated_cost_usd": self.estimated_cost_usd,
        }


@dataclass
class ToolDefinition:
    """
    Complete definition of a tool in the WAT framework.

    Tools are atomic units of execution that can be invoked by agents.
    They can be Python functions, MCP servers, or external APIs.
    """

    name: str
    description: str
    category: ToolCategory
    inputs: List[ToolInput] = field(default_factory=list)
    outputs: Optional[ToolOutput] = None
    # The actual callable (function, coroutine, or MCP tool reference)
    handler: Optional[Callable] = None
    # MCP server reference if this is an MCP tool
    mcp_server: Optional[str] = None
    # Cost estimation for this tool
    cost_estimate: Optional[CostEstimate] = None
    # Tags for filtering and discovery
    tags: List[str] = field(default_factory=list)
    # Whether this tool is async
    is_async: bool = True
    # Maximum retries for this specific tool
    max_retries: int = 3
    # Timeout in seconds
    timeout_seconds: int = 30
    # Whether this tool requires confirmation before execution
    requires_confirmation: bool = False
    # Dependencies (other tools that must be available)
    dependencies: List[str] = field(default_factory=list)
    # Version for compatibility tracking
    version: str = "1.0.0"
    # Source location for debugging
    source_file: Optional[str] = None
    source_line: Optional[int] = None

    def __hash__(self) -> int:
        """Make tool hashable for use in sets and dicts."""
        return hash(f"{self.name}:{self.version}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "inputs": [i.to_dict() for i in self.inputs],
            "outputs": self.outputs.to_dict() if self.outputs else None,
            "mcp_server": self.mcp_server,
            "cost_estimate": self.cost_estimate.to_dict() if self.cost_estimate else None,
            "tags": self.tags,
            "is_async": self.is_async,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "requires_confirmation": self.requires_confirmation,
            "dependencies": self.dependencies,
            "version": self.version,
            "source_file": self.source_file,
            "source_line": self.source_line,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolDefinition":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            description=data["description"],
            category=ToolCategory(data["category"]),
            inputs=[ToolInput(**i) for i in data.get("inputs", [])],
            outputs=ToolOutput(**data["outputs"]) if data.get("outputs") else None,
            mcp_server=data.get("mcp_server"),
            cost_estimate=CostEstimate(**data["cost_estimate"]) if data.get("cost_estimate") else None,
            tags=data.get("tags", []),
            is_async=data.get("is_async", True),
            max_retries=data.get("max_retries", 3),
            timeout_seconds=data.get("timeout_seconds", 30),
            requires_confirmation=data.get("requires_confirmation", False),
            dependencies=data.get("dependencies", []),
            version=data.get("version", "1.0.0"),
            source_file=data.get("source_file"),
            source_line=data.get("source_line"),
        )


@dataclass
class WorkflowStep:
    """
    A single step in a workflow.

    Steps reference tools by name and provide input mappings.
    """

    id: str
    tool: str  # Tool name
    description: str
    inputs: Dict[str, Any] = field(default_factory=dict)
    # Reference previous step outputs with $prev or $step_id.field
    input_mappings: Dict[str, str] = field(default_factory=dict)
    # Condition for conditional execution
    condition: Optional[str] = None
    # Error handling for this step
    on_error: Optional[str] = None  # "retry", "skip", "abort", "fallback:tool_name"
    # Maximum retries for this step
    max_retries: int = 3
    # Timeout in seconds
    timeout_seconds: int = 60

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "tool": self.tool,
            "description": self.description,
            "inputs": self.inputs,
            "input_mappings": self.input_mappings,
            "condition": self.condition,
            "on_error": self.on_error,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass
class ErrorRecoveryStrategy:
    """
    Strategy for recovering from specific error types.
    """

    error_type: ErrorType
    action: RecoveryAction
    max_attempts: int = 3
    backoff_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    fallback_tool: Optional[str] = None
    alert_severity: Optional[str] = None  # "info", "warning", "error", "critical"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "error_type": self.error_type.value,
            "action": self.action.value,
            "max_attempts": self.max_attempts,
            "backoff_seconds": self.backoff_seconds,
            "backoff_multiplier": self.backoff_multiplier,
            "fallback_tool": self.fallback_tool,
            "alert_severity": self.alert_severity,
        }


@dataclass
class WorkflowDefinition:
    """
    Complete workflow definition.

    Workflows define goals, steps, constraints, and error handling.
    """

    name: str
    description: str
    version: str = "1.0.0"
    steps: List[WorkflowStep] = field(default_factory=list)
    # Global constraints
    constraints: List[str] = field(default_factory=list)
    # Required tools for this workflow
    required_tools: List[str] = field(default_factory=list)
    # Error recovery strategies
    error_handlers: List[ErrorRecoveryStrategy] = field(default_factory=list)
    # Maximum total execution time
    timeout_seconds: int = 300
    # Maximum cost budget in USD
    cost_budget_usd: Optional[float] = None
    # Tags for categorization
    tags: List[str] = field(default_factory=list)
    # Input schema for the workflow
    inputs: Dict[str, ToolInput] = field(default_factory=dict)
    # Expected output schema
    outputs: Optional[ToolOutput] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "steps": [s.to_dict() for s in self.steps],
            "constraints": self.constraints,
            "required_tools": self.required_tools,
            "error_handlers": [e.to_dict() for e in self.error_handlers],
            "timeout_seconds": self.timeout_seconds,
            "cost_budget_usd": self.cost_budget_usd,
            "tags": self.tags,
            "inputs": {k: v.to_dict() for k, v in self.inputs.items()},
            "outputs": self.outputs.to_dict() if self.outputs else None,
        }

    def to_yaml(self) -> str:
        """Convert to YAML string."""
        import yaml

        return yaml.dump(self.to_dict(), default_flow_style=False, allow_unicode=True)


@dataclass
class AgentCapability:
    """
    A capability that an agent possesses.

    Capabilities are matched to workflow requirements.
    """

    name: str
    description: str
    # Tools that provide this capability
    provided_by: List[str] = field(default_factory=list)
    # Confidence level (0.0 to 1.0)
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "provided_by": self.provided_by,
            "confidence": self.confidence,
        }


@dataclass
class StepResult:
    """Result of executing a single workflow step."""

    step_id: str
    tool_name: str
    status: ExecutionStatus
    output: Any = None
    error: Optional[str] = None
    error_type: Optional[ErrorType] = None
    duration_ms: float = 0.0
    retries: int = 0
    cost_usd: float = 0.0
    tokens_used: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "step_id": self.step_id,
            "tool_name": self.tool_name,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "error_type": self.error_type.value if self.error_type else None,
            "duration_ms": self.duration_ms,
            "retries": self.retries,
            "cost_usd": self.cost_usd,
            "tokens_used": self.tokens_used,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ExecutionResult:
    """
    Complete result of a workflow execution.
    """

    workflow_name: str
    status: ExecutionStatus
    step_results: List[StepResult] = field(default_factory=list)
    output: Any = None
    error: Optional[str] = None
    total_duration_ms: float = 0.0
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    total_retries: int = 0
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    # Trace ID for observability
    trace_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "workflow_name": self.workflow_name,
            "status": self.status.value,
            "step_results": [s.to_dict() for s in self.step_results],
            "output": self.output,
            "error": self.error,
            "total_duration_ms": self.total_duration_ms,
            "total_cost_usd": self.total_cost_usd,
            "total_tokens": self.total_tokens,
            "total_retries": self.total_retries,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "trace_id": self.trace_id,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
