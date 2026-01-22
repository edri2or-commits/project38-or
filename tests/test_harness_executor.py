"""Tests for src/harness/executor.py - Agent Executor."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

# Skip all tests if dependencies not installed (harness/__init__.py imports psutil)
pytest.importorskip("psutil")


class TestExecutionError:
    """Tests for ExecutionError exception."""

    def test_execution_error_is_exception(self):
        """ExecutionError should be an Exception subclass."""
        from src.harness.executor import ExecutionError

        assert issubclass(ExecutionError, Exception)

    def test_execution_error_message(self):
        """ExecutionError should store message."""
        from src.harness.executor import ExecutionError

        error = ExecutionError("Execution failed")
        assert str(error) == "Execution failed"


class TestExecutionResult:
    """Tests for ExecutionResult class."""

    def test_default_values(self):
        """ExecutionResult should have sensible defaults."""
        from src.harness.executor import ExecutionResult

        result = ExecutionResult(status="success")
        assert result.status == "success"
        assert result.result == {}
        assert result.error is None
        assert result.stdout == ""
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.duration == 0.0

    def test_custom_values(self):
        """ExecutionResult should accept custom values."""
        from src.harness.executor import ExecutionResult

        result = ExecutionResult(
            status="error",
            result={"data": 42},
            error="Something went wrong",
            stdout="output",
            stderr="error output",
            exit_code=1,
            duration=5.5,
        )
        assert result.status == "error"
        assert result.result == {"data": 42}
        assert result.error == "Something went wrong"
        assert result.stdout == "output"
        assert result.stderr == "error output"
        assert result.exit_code == 1
        assert result.duration == 5.5

    def test_to_dict(self):
        """to_dict should return dictionary representation."""
        from src.harness.executor import ExecutionResult

        result = ExecutionResult(
            status="success",
            result={"key": "value"},
            error=None,
            stdout="hello",
            stderr="",
            exit_code=0,
            duration=1.2,
        )
        d = result.to_dict()

        assert d["status"] == "success"
        assert d["result"] == {"key": "value"}
        assert d["error"] is None
        assert d["stdout"] == "hello"
        assert d["stderr"] == ""
        assert d["exit_code"] == 0
        assert d["duration"] == 1.2

    def test_to_dict_all_fields(self):
        """to_dict should include all fields."""
        from src.harness.executor import ExecutionResult

        result = ExecutionResult(status="success")
        d = result.to_dict()

        expected_keys = {"status", "result", "error", "stdout", "stderr", "exit_code", "duration"}
        assert set(d.keys()) == expected_keys


class TestExecuteAgentCode:
    """Tests for execute_agent_code function."""

    @pytest.mark.asyncio
    async def test_empty_code_raises_value_error(self):
        """Empty code should raise ValueError."""
        from src.harness.executor import execute_agent_code

        with pytest.raises(ValueError, match="Agent code cannot be empty"):
            await execute_agent_code("")

    @pytest.mark.asyncio
    async def test_whitespace_code_raises_value_error(self):
        """Whitespace-only code should raise ValueError."""
        from src.harness.executor import execute_agent_code

        with pytest.raises(ValueError, match="Agent code cannot be empty"):
            await execute_agent_code("   \n  ")

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Successful agent should return success status."""
        from src.harness.executor import execute_agent_code

        agent_code = '''
class Agent:
    def __init__(self, config):
        self.config = config

    async def execute(self):
        return {"status": "success", "result": "Hello"}
'''
        result = await execute_agent_code(agent_code, config={})
        assert result.status == "success"
        assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_config_passed_to_agent(self):
        """Config should be passed to agent."""
        from src.harness.executor import execute_agent_code

        agent_code = '''
class Agent:
    def __init__(self, config):
        self.config = config

    async def execute(self):
        return {"status": "success", "result": self.config.get("key")}
'''
        result = await execute_agent_code(agent_code, config={"key": "test_value"})
        assert result.status == "success"
        assert result.result.get("result") == "test_value"

    @pytest.mark.asyncio
    async def test_agent_error_returns_error_status(self):
        """Agent raising exception should return error status."""
        from src.harness.executor import execute_agent_code

        agent_code = '''
class Agent:
    def __init__(self, config):
        pass

    async def execute(self):
        raise ValueError("Agent error")
'''
        result = await execute_agent_code(agent_code, config={})
        assert result.status == "error"
        assert result.exit_code != 0
        assert "Agent error" in result.error or "ValueError" in result.stderr

    @pytest.mark.asyncio
    async def test_timeout_returns_timeout_status(self):
        """Agent exceeding timeout should return timeout status."""
        from src.harness.executor import execute_agent_code

        agent_code = '''
import asyncio

class Agent:
    def __init__(self, config):
        pass

    async def execute(self):
        await asyncio.sleep(10)  # Sleep longer than timeout
        return {"status": "success"}
'''
        result = await execute_agent_code(agent_code, config={}, timeout=1)
        assert result.status == "timeout"
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_default_timeout(self):
        """Default timeout should be 300 seconds."""
        from src.harness.executor import execute_agent_code

        agent_code = '''
class Agent:
    def __init__(self, config):
        pass

    async def execute(self):
        return {"status": "success", "result": "done"}
'''
        # We can't easily test the full 300s timeout, but we can verify the function accepts it
        result = await execute_agent_code(agent_code, config={}, timeout=300)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_cleanup_called(self):
        """Cleanup method should be called if exists."""
        from src.harness.executor import execute_agent_code

        # Since cleanup runs in subprocess, we verify it doesn't cause errors
        agent_code = '''
class Agent:
    def __init__(self, config):
        pass

    async def execute(self):
        return {"status": "success", "result": "done"}

    async def cleanup(self):
        pass  # Cleanup runs without error
'''
        result = await execute_agent_code(agent_code, config={})
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_duration_recorded(self):
        """Execution duration should be recorded."""
        from src.harness.executor import execute_agent_code

        agent_code = '''
import asyncio

class Agent:
    def __init__(self, config):
        pass

    async def execute(self):
        await asyncio.sleep(0.1)
        return {"status": "success"}
'''
        result = await execute_agent_code(agent_code, config={})
        assert result.duration >= 0.1

    @pytest.mark.asyncio
    async def test_syntax_error_returns_error(self):
        """Syntax error in agent code should return error."""
        from src.harness.executor import execute_agent_code

        agent_code = '''
class Agent
    def __init__(self, config):  # Missing colon above
        pass
'''
        result = await execute_agent_code(agent_code, config={})
        assert result.status == "error"
        assert result.exit_code != 0

    @pytest.mark.asyncio
    async def test_missing_agent_class_returns_error(self):
        """Missing Agent class should return error."""
        from src.harness.executor import execute_agent_code

        agent_code = '''
def hello():
    return "hello"
'''
        result = await execute_agent_code(agent_code, config={})
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_none_config_defaults_to_empty_dict(self):
        """None config should default to empty dict."""
        from src.harness.executor import execute_agent_code

        agent_code = '''
class Agent:
    def __init__(self, config):
        self.config = config

    async def execute(self):
        return {"status": "success", "result": len(self.config)}
'''
        result = await execute_agent_code(agent_code, config=None)
        assert result.status == "success"
        assert result.result.get("result") == 0

    @pytest.mark.asyncio
    async def test_result_json_parsed(self):
        """Agent result should be JSON parsed."""
        from src.harness.executor import execute_agent_code

        agent_code = '''
class Agent:
    def __init__(self, config):
        pass

    async def execute(self):
        return {"status": "success", "data": [1, 2, 3], "nested": {"key": "value"}}
'''
        result = await execute_agent_code(agent_code, config={})
        assert result.status == "success"
        assert result.result.get("data") == [1, 2, 3]
        assert result.result.get("nested") == {"key": "value"}
