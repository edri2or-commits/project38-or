"""
Tests for WAT Framework Components

Tests cover:
- ToolRegistry: Registration, discovery, search
- Workflow: YAML/Markdown parsing, validation
- AgentDefinition: Capability matching, routing
- SelfHealingExecutor: Error recovery, execution flow
"""

import asyncio
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.wat.types import (
    AgentCapability,
    CostEstimate,
    ErrorRecoveryStrategy,
    ErrorType,
    ExecutionStatus,
    RecoveryAction,
    ToolCategory,
    ToolDefinition,
    ToolInput,
    ToolOutput,
    WorkflowDefinition,
    WorkflowStep,
)
from src.wat.registry import ToolRegistry, tool_definition
from src.wat.workflow import Workflow, WorkflowEngine
from src.wat.agent import AgentDefinition, AgentDispatcher, AgentDomain, ModelTier
from src.wat.executor import (
    ErrorClassifier,
    ExecutionContext,
    SelfHealingExecutor,
)


# =============================================================================
# ToolRegistry Tests
# =============================================================================


class TestToolDefinition:
    """Tests for ToolDefinition dataclass."""

    def test_create_minimal(self):
        """Test creating a minimal tool definition."""
        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            category=ToolCategory.GENERAL,
        )
        assert tool.name == "test_tool"
        assert tool.category == ToolCategory.GENERAL
        assert tool.is_async is True
        assert tool.max_retries == 3

    def test_create_full(self):
        """Test creating a full tool definition."""
        tool = ToolDefinition(
            name="search_places",
            description="Search for places using Google Maps",
            category=ToolCategory.DATA,
            inputs=[
                ToolInput(
                    name="query",
                    type="str",
                    description="Search query",
                    required=True,
                ),
                ToolInput(
                    name="location",
                    type="str",
                    description="Location",
                    required=False,
                    default="San Francisco",
                ),
            ],
            outputs=ToolOutput(
                type="list",
                description="List of places",
            ),
            cost_estimate=CostEstimate(
                model="claude-3-5-sonnet",
                estimated_cost_usd=0.001,
            ),
            tags=["google", "maps", "search"],
        )
        assert len(tool.inputs) == 2
        assert tool.outputs.type == "list"
        assert len(tool.tags) == 3

    def test_to_dict_roundtrip(self):
        """Test serialization and deserialization."""
        original = ToolDefinition(
            name="test",
            description="Test tool",
            category=ToolCategory.DATA,
            tags=["test"],
        )
        data = original.to_dict()
        restored = ToolDefinition.from_dict(data)
        assert restored.name == original.name
        assert restored.category == original.category

    def test_hash(self):
        """Test tool hashing for use in sets."""
        tool1 = ToolDefinition(
            name="test",
            description="Test",
            category=ToolCategory.GENERAL,
        )
        tool2 = ToolDefinition(
            name="test",
            description="Different",
            category=ToolCategory.DATA,
        )
        # Same name, same version = same hash
        assert hash(tool1) == hash(tool2)


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_register_tool(self):
        """Test registering a tool."""
        registry = ToolRegistry()
        tool = ToolDefinition(
            name="my_tool",
            description="My tool",
            category=ToolCategory.DATA,
        )
        registry.register(tool)

        assert registry.get("my_tool") is not None
        assert registry.get("my_tool").name == "my_tool"

    def test_get_by_category(self):
        """Test getting tools by category."""
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="data1", description="Data 1", category=ToolCategory.DATA
            )
        )
        registry.register(
            ToolDefinition(
                name="data2", description="Data 2", category=ToolCategory.DATA
            )
        )
        registry.register(
            ToolDefinition(
                name="deploy1", description="Deploy 1", category=ToolCategory.DEPLOYMENT
            )
        )

        data_tools = registry.get_by_category(ToolCategory.DATA)
        assert len(data_tools) == 2

    def test_get_by_tag(self):
        """Test getting tools by tag."""
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="google_maps",
                description="Google Maps",
                category=ToolCategory.DATA,
                tags=["google", "maps"],
            )
        )
        registry.register(
            ToolDefinition(
                name="google_drive",
                description="Google Drive",
                category=ToolCategory.STORAGE,
                tags=["google", "drive"],
            )
        )

        google_tools = registry.get_by_tag("google")
        assert len(google_tools) == 2

    def test_search(self):
        """Test searching for tools."""
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="search_places",
                description="Search for places on map",
                category=ToolCategory.DATA,
            )
        )
        registry.register(
            ToolDefinition(
                name="search_files",
                description="Search for files",
                category=ToolCategory.STORAGE,
            )
        )

        results = registry.search("places")
        assert len(results) == 1
        assert results[0].name == "search_places"

    def test_validate_dependencies(self):
        """Test dependency validation."""
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="tool_a",
                description="Tool A",
                category=ToolCategory.GENERAL,
            )
        )
        registry.register(
            ToolDefinition(
                name="tool_b",
                description="Tool B",
                category=ToolCategory.GENERAL,
                dependencies=["tool_a", "tool_c"],  # tool_c doesn't exist
            )
        )

        missing = registry.validate_dependencies(["tool_b"])
        assert "tool_b" in missing
        assert "tool_c" in missing["tool_b"]

    def test_unregister(self):
        """Test unregistering a tool."""
        registry = ToolRegistry()
        tool = ToolDefinition(
            name="temp_tool",
            description="Temporary",
            category=ToolCategory.GENERAL,
        )
        registry.register(tool)
        assert registry.get("temp_tool") is not None

        result = registry.unregister("temp_tool")
        assert result is True
        assert registry.get("temp_tool") is None


class TestToolDefinitionDecorator:
    """Tests for @tool_definition decorator."""

    def test_decorator_basic(self):
        """Test basic decorator usage."""

        @tool_definition(
            name="decorated_tool",
            category=ToolCategory.DATA,
        )
        async def my_tool(query: str) -> str:
            """Search for something."""
            return f"Result for {query}"

        assert hasattr(my_tool, "__wat_tool__")
        tool_def = my_tool.__wat_tool__
        assert tool_def.name == "decorated_tool"
        assert tool_def.category == ToolCategory.DATA
        assert tool_def.is_async is True

    def test_decorator_extracts_inputs(self):
        """Test that decorator extracts input parameters."""

        @tool_definition(category=ToolCategory.GENERAL)
        def process_data(
            data: str,
            format: str = "json",
        ) -> dict:
            """Process data."""
            return {}

        tool_def = process_data.__wat_tool__
        assert len(tool_def.inputs) == 2
        assert tool_def.inputs[0].name == "data"
        assert tool_def.inputs[0].required is True
        assert tool_def.inputs[1].name == "format"
        assert tool_def.inputs[1].default == "json"


# =============================================================================
# Workflow Tests
# =============================================================================


class TestWorkflowStep:
    """Tests for WorkflowStep."""

    def test_create_step(self):
        """Test creating a workflow step."""
        step = WorkflowStep(
            id="search",
            tool="search_places",
            description="Search for businesses",
            inputs={"query": "Dentist"},
        )
        assert step.id == "search"
        assert step.tool == "search_places"

    def test_step_with_mappings(self):
        """Test step with input mappings."""
        step = WorkflowStep(
            id="enrich",
            tool="enrich_data",
            description="Enrich data",
            input_mappings={
                "data": "$prev.output",
                "config": "$inputs.config",
            },
        )
        assert step.input_mappings["data"] == "$prev.output"


class TestWorkflow:
    """Tests for Workflow class."""

    def test_from_dict(self):
        """Test creating workflow from dictionary."""
        data = {
            "name": "test-workflow",
            "description": "A test workflow",
            "steps": [
                {
                    "id": "step1",
                    "tool": "tool1",
                    "description": "First step",
                }
            ],
            "constraints": ["Do not fail"],
        }
        workflow = Workflow.from_dict(data)
        assert workflow.name == "test-workflow"
        assert len(workflow.steps) == 1
        assert len(workflow.definition.constraints) == 1

    def test_from_yaml_string(self, tmp_path):
        """Test loading workflow from YAML file."""
        yaml_content = """
name: yaml-workflow
description: Workflow from YAML
version: "1.0.0"
steps:
  - id: first
    tool: search
    description: Search for data
  - id: second
    tool: process
    description: Process results
    input_mappings:
      data: "$prev.output"
constraints:
  - "Be careful"
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        workflow = Workflow.from_yaml(yaml_file)
        assert workflow.name == "yaml-workflow"
        assert len(workflow.steps) == 2
        assert workflow.steps[1].input_mappings["data"] == "$prev.output"

    def test_validate_success(self):
        """Test workflow validation success."""
        workflow = Workflow.from_dict({
            "name": "valid",
            "description": "Valid workflow",
            "steps": [
                {"id": "s1", "tool": "tool_a", "description": "Step 1"},
            ],
        })
        errors = workflow.validate(["tool_a", "tool_b"])
        assert len(errors) == 0

    def test_validate_missing_tool(self):
        """Test workflow validation with missing tool."""
        workflow = Workflow.from_dict({
            "name": "invalid",
            "description": "Invalid workflow",
            "steps": [
                {"id": "s1", "tool": "missing_tool", "description": "Step 1"},
            ],
        })
        errors = workflow.validate(["tool_a"])
        assert len(errors) == 1
        assert "missing_tool" in errors[0]

    def test_to_prompt(self):
        """Test converting workflow to prompt."""
        workflow = Workflow.from_dict({
            "name": "prompt-test",
            "description": "Generate leads",
            "steps": [
                {"id": "search", "tool": "search_places", "description": "Find places"},
            ],
            "constraints": ["Be accurate"],
        })
        prompt = workflow.to_prompt()
        assert "prompt-test" in prompt
        assert "search_places" in prompt
        assert "Be accurate" in prompt


class TestWorkflowEngine:
    """Tests for WorkflowEngine."""

    def test_register_and_get(self):
        """Test registering and retrieving workflows."""
        engine = WorkflowEngine()
        workflow = Workflow.from_dict({
            "name": "my-workflow",
            "description": "Test",
            "steps": [],
        })
        engine.register(workflow)
        retrieved = engine.get("my-workflow")
        assert retrieved is not None
        assert retrieved.name == "my-workflow"

    def test_list_workflows(self):
        """Test listing workflows."""
        engine = WorkflowEngine()
        engine.register(Workflow.from_dict({"name": "wf1", "description": "", "steps": []}))
        engine.register(Workflow.from_dict({"name": "wf2", "description": "", "steps": []}))

        names = engine.list()
        assert len(names) == 2
        assert "wf1" in names
        assert "wf2" in names


# =============================================================================
# Agent Tests
# =============================================================================


class TestAgentDefinition:
    """Tests for AgentDefinition."""

    def test_create_agent(self):
        """Test creating an agent definition."""
        agent = AgentDefinition(
            name="deploy-agent",
            description="Handles deployments",
            domain=AgentDomain.DEPLOYMENT,
            tools=["railway_deploy", "railway_status"],
        )
        assert agent.name == "deploy-agent"
        assert agent.domain == AgentDomain.DEPLOYMENT
        assert len(agent.tools) == 2

    def test_auto_capabilities(self):
        """Test automatic capability generation from tools."""
        agent = AgentDefinition(
            name="test-agent",
            description="Test",
            tools=["tool_a", "tool_b"],
        )
        # Should auto-generate capabilities
        assert len(agent.capabilities) == 2
        assert agent.has_capability("can_use_tool_a")

    def test_can_handle_workflow(self):
        """Test workflow handling score calculation."""
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="deploy", description="Deploy", category=ToolCategory.DEPLOYMENT
            )
        )
        registry.register(
            ToolDefinition(
                name="status", description="Status", category=ToolCategory.MONITORING
            )
        )

        agent = AgentDefinition(
            name="deploy-agent",
            description="Deploys",
            domain=AgentDomain.DEPLOYMENT,
            tools=["deploy", "status"],
        )

        workflow_def = WorkflowDefinition(
            name="deploy-workflow",
            description="Deploy something",
            steps=[
                WorkflowStep(id="s1", tool="deploy", description="Deploy"),
            ],
            required_tools=["deploy"],
        )

        score = agent.can_handle(workflow_def, registry)
        assert score > 0.5  # Should have high score due to tool + domain match


class TestAgentDispatcher:
    """Tests for AgentDispatcher."""

    def test_register_and_get(self):
        """Test registering and getting agents."""
        registry = ToolRegistry()
        dispatcher = AgentDispatcher(registry)

        agent = AgentDefinition(
            name="test-agent",
            description="Test",
            domain=AgentDomain.GENERAL,
        )
        dispatcher.register(agent)

        retrieved = dispatcher.get("test-agent")
        assert retrieved is not None
        assert retrieved.name == "test-agent"

    def test_get_by_domain(self):
        """Test getting agents by domain."""
        registry = ToolRegistry()
        dispatcher = AgentDispatcher(registry)

        dispatcher.register(AgentDefinition(
            name="deploy1",
            description="Deploy 1",
            domain=AgentDomain.DEPLOYMENT,
        ))
        dispatcher.register(AgentDefinition(
            name="monitor1",
            description="Monitor 1",
            domain=AgentDomain.MONITORING,
        ))

        deploy_agents = dispatcher.get_by_domain(AgentDomain.DEPLOYMENT)
        assert len(deploy_agents) == 1
        assert deploy_agents[0].name == "deploy1"

    def test_find_best_agent(self):
        """Test finding best agent for workflow."""
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="railway_deploy",
                description="Deploy",
                category=ToolCategory.DEPLOYMENT,
            )
        )

        dispatcher = AgentDispatcher(registry)
        dispatcher.register(AgentDefinition(
            name="deploy-agent",
            description="Deployment specialist",
            domain=AgentDomain.DEPLOYMENT,
            tools=["railway_deploy"],
        ))
        dispatcher.register(AgentDefinition(
            name="general-agent",
            description="General purpose",
            domain=AgentDomain.GENERAL,
            tools=[],
        ))

        workflow_def = WorkflowDefinition(
            name="deploy-wf",
            description="Deploy app",
            required_tools=["railway_deploy"],
        )

        best = dispatcher.find_best_agent(workflow_def)
        assert best is not None
        assert best.name == "deploy-agent"


# =============================================================================
# Executor Tests
# =============================================================================


class TestErrorClassifier:
    """Tests for ErrorClassifier."""

    def test_classify_network_error(self):
        """Test classifying network errors."""
        error = ConnectionRefusedError("Connection refused")
        error_type = ErrorClassifier.classify(error)
        assert error_type == ErrorType.NETWORK

    def test_classify_rate_limit(self):
        """Test classifying rate limit errors."""
        error = Exception("429 Too Many Requests")
        error_type = ErrorClassifier.classify(error)
        assert error_type == ErrorType.RATE_LIMIT

    def test_classify_auth_error(self):
        """Test classifying authentication errors."""
        error = Exception("401 Unauthorized: Invalid token")
        error_type = ErrorClassifier.classify(error)
        assert error_type == ErrorType.AUTHENTICATION

    def test_classify_dependency_error(self):
        """Test classifying dependency errors."""
        error = ModuleNotFoundError("No module named 'pandas'")
        error_type = ErrorClassifier.classify(error)
        assert error_type == ErrorType.DEPENDENCY

    def test_classify_unknown(self):
        """Test classifying unknown errors."""
        error = Exception("Something weird happened")
        error_type = ErrorClassifier.classify(error)
        assert error_type == ErrorType.UNKNOWN


class TestExecutionContext:
    """Tests for ExecutionContext."""

    def test_get_reference_inputs(self):
        """Test getting input references."""
        context = ExecutionContext(
            workflow=WorkflowDefinition(
                name="test", description="Test"
            ),
            agent=AgentDefinition(name="test", description="Test"),
            inputs={"location": "San Francisco"},
        )

        value = context.get_reference("$inputs.location")
        assert value == "San Francisco"

    def test_get_reference_prev(self):
        """Test getting previous step reference."""
        from src.wat.types import StepResult

        context = ExecutionContext(
            workflow=WorkflowDefinition(name="test", description="Test"),
            agent=AgentDefinition(name="test", description="Test"),
        )
        context.step_results["step1"] = StepResult(
            step_id="step1",
            tool_name="tool1",
            status=ExecutionStatus.SUCCESS,
            output={"data": [1, 2, 3]},
        )

        value = context.get_reference("$prev.output")
        assert value == {"data": [1, 2, 3]}


class TestSelfHealingExecutor:
    """Tests for SelfHealingExecutor."""

    @pytest.fixture
    def registry(self):
        """Create a test registry with mock tools."""
        registry = ToolRegistry()

        async def success_tool(**kwargs):
            return {"status": "success", "data": kwargs}

        registry.register(
            ToolDefinition(
                name="success_tool",
                description="Always succeeds",
                category=ToolCategory.GENERAL,
                handler=success_tool,
                is_async=True,
            )
        )

        return registry

    @pytest.fixture
    def agent(self):
        """Create a test agent."""
        return AgentDefinition(
            name="test-agent",
            description="Test agent",
            tools=["success_tool"],
        )

    @pytest.mark.asyncio
    async def test_execute_success(self, registry, agent):
        """Test successful workflow execution."""
        executor = SelfHealingExecutor(registry)

        workflow = Workflow.from_dict({
            "name": "simple-workflow",
            "description": "Simple test",
            "steps": [
                {
                    "id": "step1",
                    "tool": "success_tool",
                    "description": "Run success tool",
                    "inputs": {"key": "value"},
                }
            ],
        })

        result = await executor.run(workflow, agent, inputs={})

        assert result.status == ExecutionStatus.SUCCESS
        assert len(result.step_results) == 1
        assert result.step_results[0].status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_execute_with_retry(self, registry, agent):
        """Test execution with retry on failure."""
        call_count = 0

        async def flaky_tool(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network error")
            return {"status": "success"}

        registry.register(
            ToolDefinition(
                name="flaky_tool",
                description="Fails twice then succeeds",
                category=ToolCategory.GENERAL,
                handler=flaky_tool,
                is_async=True,
            )
        )

        agent.tools.append("flaky_tool")

        workflow = Workflow.from_dict({
            "name": "retry-workflow",
            "description": "Tests retry",
            "steps": [
                {
                    "id": "step1",
                    "tool": "flaky_tool",
                    "description": "Flaky step",
                    "max_retries": 5,
                }
            ],
        })

        result = await executor.run(workflow, agent, inputs={})

        assert result.status == ExecutionStatus.SUCCESS
        assert call_count == 3  # Failed twice, succeeded on third try

    @pytest.mark.asyncio
    async def test_execute_missing_tool(self, registry, agent):
        """Test execution with missing tool."""
        executor = SelfHealingExecutor(registry)

        workflow = Workflow.from_dict({
            "name": "missing-tool-workflow",
            "description": "Has missing tool",
            "steps": [
                {
                    "id": "step1",
                    "tool": "nonexistent_tool",
                    "description": "This tool doesn't exist",
                }
            ],
        })

        result = await executor.run(workflow, agent, inputs={})

        assert result.status == ExecutionStatus.FAILED
        assert "not found" in result.step_results[0].error

    @pytest.mark.asyncio
    async def test_execute_with_condition(self, registry, agent):
        """Test conditional step execution."""
        executor = SelfHealingExecutor(registry)

        workflow = Workflow.from_dict({
            "name": "conditional-workflow",
            "description": "Has conditional steps",
            "steps": [
                {
                    "id": "step1",
                    "tool": "success_tool",
                    "description": "Always runs",
                },
                {
                    "id": "step2",
                    "tool": "success_tool",
                    "description": "Conditional step",
                    "condition": "$inputs.run_step2 == True",
                },
            ],
        })

        # Without condition
        result1 = await executor.run(
            workflow, agent, inputs={"run_step2": False}
        )
        assert len([s for s in result1.step_results if s.status == ExecutionStatus.SUCCESS]) == 1

        # With condition
        result2 = await executor.run(
            workflow, agent, inputs={"run_step2": True}
        )
        assert len([s for s in result2.step_results if s.status == ExecutionStatus.SUCCESS]) == 2


# =============================================================================
# Integration Tests
# =============================================================================


class TestWATIntegration:
    """Integration tests for WAT Framework components."""

    @pytest.mark.asyncio
    async def test_full_workflow_execution(self):
        """Test complete workflow from registration to execution."""
        # Setup registry
        registry = ToolRegistry()

        async def mock_search(query: str, location: str = "SF"):
            return {"places": [{"id": "1", "name": f"Result for {query}"}]}

        async def mock_enrich(place_id: str):
            return {"id": place_id, "email": "test@example.com"}

        registry.register(ToolDefinition(
            name="search",
            description="Search places",
            category=ToolCategory.DATA,
            handler=mock_search,
            is_async=True,
        ))
        registry.register(ToolDefinition(
            name="enrich",
            description="Enrich data",
            category=ToolCategory.DATA,
            handler=mock_enrich,
            is_async=True,
        ))

        # Setup agent
        agent = AgentDefinition(
            name="data-agent",
            description="Handles data operations",
            domain=AgentDomain.DATA,
            tools=["search", "enrich"],
        )

        # Setup workflow
        workflow = Workflow.from_dict({
            "name": "integration-test",
            "description": "Full integration test",
            "steps": [
                {
                    "id": "find",
                    "tool": "search",
                    "description": "Find places",
                    "inputs": {"query": "Dentist"},
                },
                {
                    "id": "enrich",
                    "tool": "enrich",
                    "description": "Get details",
                    "inputs": {"place_id": "1"},
                },
            ],
        })

        # Execute
        executor = SelfHealingExecutor(registry)
        result = await executor.run(workflow, agent, inputs={})

        # Verify
        assert result.status == ExecutionStatus.SUCCESS
        assert len(result.step_results) == 2
        assert result.output["email"] == "test@example.com"

    def test_registry_workflow_agent_integration(self):
        """Test integration between registry, workflow, and agent."""
        # Create registry with tools
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="deploy", description="Deploy", category=ToolCategory.DEPLOYMENT
        ))
        registry.register(ToolDefinition(
            name="monitor", description="Monitor", category=ToolCategory.MONITORING
        ))

        # Create agents
        dispatcher = AgentDispatcher(registry)
        dispatcher.register(AgentDefinition(
            name="deploy-agent",
            description="Deploys",
            domain=AgentDomain.DEPLOYMENT,
            tools=["deploy"],
        ))
        dispatcher.register(AgentDefinition(
            name="monitor-agent",
            description="Monitors",
            domain=AgentDomain.MONITORING,
            tools=["monitor"],
        ))

        # Create workflow requiring deploy
        workflow = Workflow.from_dict({
            "name": "deploy-workflow",
            "description": "Deploy app",
            "steps": [
                {"id": "s1", "tool": "deploy", "description": "Deploy"},
            ],
        })

        # Validate workflow
        errors = workflow.validate(["deploy", "monitor"])
        assert len(errors) == 0

        # Find best agent
        agents = dispatcher.route(workflow.definition)
        assert len(agents) >= 1
        assert agents[0].name == "deploy-agent"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
