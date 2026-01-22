"""Tests for src/harness/handoff.py - Handoff Artifacts."""

import pytest
from datetime import datetime, UTC
import json

# Skip all tests if dependencies not installed (harness/__init__.py imports psutil)
pytest.importorskip("psutil")


class TestHandoffArtifact:
    """Tests for HandoffArtifact dataclass."""

    def test_default_values(self):
        """HandoffArtifact should have sensible defaults."""
        from src.harness.handoff import HandoffArtifact

        artifact = HandoffArtifact(agent_id=1)
        assert artifact.agent_id == 1
        assert artifact.run_number == 1
        assert artifact.state == {}
        assert artifact.metadata == {}
        assert artifact.compressed is False
        assert artifact.summary == ""
        assert isinstance(artifact.created_at, datetime)

    def test_custom_values(self):
        """HandoffArtifact should accept custom values."""
        from src.harness.handoff import HandoffArtifact

        now = datetime.now(UTC)
        artifact = HandoffArtifact(
            agent_id=42,
            run_number=5,
            state={"count": 100},
            metadata={"duration": 10.5},
            created_at=now,
            compressed=True,
            summary="Run completed",
        )
        assert artifact.agent_id == 42
        assert artifact.run_number == 5
        assert artifact.state == {"count": 100}
        assert artifact.metadata == {"duration": 10.5}
        assert artifact.created_at == now
        assert artifact.compressed is True
        assert artifact.summary == "Run completed"

    def test_to_dict(self):
        """to_dict should return dictionary representation."""
        from src.harness.handoff import HandoffArtifact

        artifact = HandoffArtifact(
            agent_id=1,
            run_number=2,
            state={"key": "value"},
            metadata={"meta": "data"},
            summary="Test run",
        )
        d = artifact.to_dict()

        assert d["agent_id"] == 1
        assert d["run_number"] == 2
        assert d["state"] == {"key": "value"}
        assert d["metadata"] == {"meta": "data"}
        assert d["summary"] == "Test run"
        assert "created_at" in d

    def test_to_dict_created_at_is_iso_format(self):
        """to_dict should convert created_at to ISO format."""
        from src.harness.handoff import HandoffArtifact

        artifact = HandoffArtifact(agent_id=1)
        d = artifact.to_dict()

        # Should be a string in ISO format
        assert isinstance(d["created_at"], str)
        # Should be parseable
        datetime.fromisoformat(d["created_at"])

    def test_to_json(self):
        """to_json should return JSON string."""
        from src.harness.handoff import HandoffArtifact

        artifact = HandoffArtifact(agent_id=1, state={"key": "value"})
        json_str = artifact.to_json()

        # Should be valid JSON
        data = json.loads(json_str)
        assert data["agent_id"] == 1
        assert data["state"] == {"key": "value"}

    def test_from_dict(self):
        """from_dict should deserialize artifact."""
        from src.harness.handoff import HandoffArtifact

        data = {
            "agent_id": 5,
            "run_number": 3,
            "state": {"data": [1, 2, 3]},
            "metadata": {},
            "created_at": "2026-01-22T10:00:00+00:00",
            "compressed": False,
            "summary": "Test",
        }
        artifact = HandoffArtifact.from_dict(data)

        assert artifact.agent_id == 5
        assert artifact.run_number == 3
        assert artifact.state == {"data": [1, 2, 3]}
        assert artifact.summary == "Test"

    def test_from_dict_minimal(self):
        """from_dict should handle minimal data."""
        from src.harness.handoff import HandoffArtifact

        data = {"agent_id": 1}
        artifact = HandoffArtifact.from_dict(data)

        assert artifact.agent_id == 1
        assert artifact.run_number == 1
        assert artifact.state == {}

    def test_from_json(self):
        """from_json should deserialize from JSON string."""
        from src.harness.handoff import HandoffArtifact

        json_str = '{"agent_id": 10, "run_number": 2, "state": {"x": 42}}'
        artifact = HandoffArtifact.from_json(json_str)

        assert artifact.agent_id == 10
        assert artifact.run_number == 2
        assert artifact.state == {"x": 42}

    def test_from_json_invalid_raises(self):
        """from_json should raise on invalid JSON."""
        from src.harness.handoff import HandoffArtifact

        with pytest.raises(json.JSONDecodeError):
            HandoffArtifact.from_json("not valid json")

    def test_roundtrip_dict(self):
        """to_dict and from_dict should roundtrip."""
        from src.harness.handoff import HandoffArtifact

        original = HandoffArtifact(
            agent_id=7,
            run_number=10,
            state={"nested": {"deep": "value"}},
            summary="Complete",
        )
        data = original.to_dict()
        restored = HandoffArtifact.from_dict(data)

        assert restored.agent_id == original.agent_id
        assert restored.run_number == original.run_number
        assert restored.state == original.state
        assert restored.summary == original.summary

    def test_roundtrip_json(self):
        """to_json and from_json should roundtrip."""
        from src.harness.handoff import HandoffArtifact

        original = HandoffArtifact(agent_id=3, state={"list": [1, 2, 3]})
        json_str = original.to_json()
        restored = HandoffArtifact.from_json(json_str)

        assert restored.agent_id == original.agent_id
        assert restored.state == original.state


class TestHandoffManager:
    """Tests for HandoffManager class."""

    def test_init(self):
        """HandoffManager should initialize empty."""
        from src.harness.handoff import HandoffManager

        manager = HandoffManager()
        assert manager._artifacts == {}

    @pytest.mark.asyncio
    async def test_save_artifact(self):
        """save_artifact should store artifact."""
        from src.harness.handoff import HandoffManager, HandoffArtifact

        manager = HandoffManager()
        artifact = HandoffArtifact(agent_id=1, state={"key": "value"})

        await manager.save_artifact(artifact)

        assert 1 in manager._artifacts
        assert manager._artifacts[1].state == {"key": "value"}

    @pytest.mark.asyncio
    async def test_save_overwrites(self):
        """save_artifact should overwrite existing artifact."""
        from src.harness.handoff import HandoffManager, HandoffArtifact

        manager = HandoffManager()
        artifact1 = HandoffArtifact(agent_id=1, state={"version": 1})
        artifact2 = HandoffArtifact(agent_id=1, state={"version": 2})

        await manager.save_artifact(artifact1)
        await manager.save_artifact(artifact2)

        assert manager._artifacts[1].state == {"version": 2}

    @pytest.mark.asyncio
    async def test_load_artifact_exists(self):
        """load_artifact should return existing artifact."""
        from src.harness.handoff import HandoffManager, HandoffArtifact

        manager = HandoffManager()
        artifact = HandoffArtifact(agent_id=5, run_number=3)
        await manager.save_artifact(artifact)

        loaded = await manager.load_artifact(5)

        assert loaded is not None
        assert loaded.agent_id == 5
        assert loaded.run_number == 3

    @pytest.mark.asyncio
    async def test_load_artifact_not_exists(self):
        """load_artifact should return None for non-existent agent."""
        from src.harness.handoff import HandoffManager

        manager = HandoffManager()
        loaded = await manager.load_artifact(999)

        assert loaded is None

    @pytest.mark.asyncio
    async def test_create_next_artifact_first_run(self):
        """create_next_artifact should create first artifact."""
        from src.harness.handoff import HandoffManager

        manager = HandoffManager()
        result = {"data": "test"}

        artifact = await manager.create_next_artifact(1, result)

        assert artifact.agent_id == 1
        assert artifact.run_number == 1
        assert artifact.state["current_result"] == result

    @pytest.mark.asyncio
    async def test_create_next_artifact_increments_run_number(self):
        """create_next_artifact should increment run number."""
        from src.harness.handoff import HandoffManager, HandoffArtifact

        manager = HandoffManager()
        first = HandoffArtifact(agent_id=1, run_number=5, state={"old": "state"})
        await manager.save_artifact(first)

        artifact = await manager.create_next_artifact(1, {"new": "result"})

        assert artifact.run_number == 6

    @pytest.mark.asyncio
    async def test_create_next_artifact_preserves_previous_state(self):
        """create_next_artifact should preserve previous state."""
        from src.harness.handoff import HandoffManager, HandoffArtifact

        manager = HandoffManager()
        first = HandoffArtifact(agent_id=1, state={"previous_data": "value"})
        await manager.save_artifact(first)

        artifact = await manager.create_next_artifact(1, {"new": "result"})

        assert artifact.state["previous_run"] == {"previous_data": "value"}

    @pytest.mark.asyncio
    async def test_create_next_artifact_includes_metadata(self):
        """create_next_artifact should include execution metadata."""
        from src.harness.handoff import HandoffManager

        manager = HandoffManager()
        metadata = {"duration": 5.5, "status": "success"}

        artifact = await manager.create_next_artifact(1, {"result": "data"}, metadata)

        assert artifact.metadata == metadata

    @pytest.mark.asyncio
    async def test_create_next_artifact_auto_saves(self):
        """create_next_artifact should auto-save artifact."""
        from src.harness.handoff import HandoffManager

        manager = HandoffManager()
        await manager.create_next_artifact(1, {"data": "test"})

        loaded = await manager.load_artifact(1)
        assert loaded is not None

    @pytest.mark.asyncio
    async def test_clear_artifact(self):
        """clear_artifact should remove artifact."""
        from src.harness.handoff import HandoffManager, HandoffArtifact

        manager = HandoffManager()
        artifact = HandoffArtifact(agent_id=1)
        await manager.save_artifact(artifact)

        await manager.clear_artifact(1)

        assert 1 not in manager._artifacts

    @pytest.mark.asyncio
    async def test_clear_artifact_non_existent(self):
        """clear_artifact should handle non-existent agent."""
        from src.harness.handoff import HandoffManager

        manager = HandoffManager()
        # Should not raise
        await manager.clear_artifact(999)

    def test_compress_state_small(self):
        """compress_state should not compress small state."""
        from src.harness.handoff import HandoffManager

        manager = HandoffManager()
        state = {"key": "value"}

        compressed = manager.compress_state(state, max_size=10000)

        assert compressed == state

    def test_compress_state_truncates_lists(self):
        """compress_state should truncate large lists."""
        from src.harness.handoff import HandoffManager

        manager = HandoffManager()
        state = {"logs": list(range(500))}  # 500 items

        compressed = manager.compress_state(state, max_size=100)

        assert len(compressed["logs"]) <= 100

    def test_compress_state_keeps_essential_keys(self):
        """compress_state should keep essential keys."""
        from src.harness.handoff import HandoffManager

        manager = HandoffManager()
        state = {
            "status": "success",
            "error": None,
            "count": 42,
            "last_value": "test",
            "large_data": "x" * 100000,
        }

        compressed = manager.compress_state(state, max_size=100)

        assert "status" in compressed
        assert compressed["status"] == "success"
        assert "count" in compressed
        assert compressed["count"] == 42

    def test_compress_state_adds_markers(self):
        """compress_state should add compression markers."""
        from src.harness.handoff import HandoffManager

        manager = HandoffManager()
        state = {"data": "x" * 100000}

        compressed = manager.compress_state(state, max_size=100)

        assert compressed.get("_compressed") is True
        assert "_original_size" in compressed


class TestGetHandoffManager:
    """Tests for get_handoff_manager function."""

    def test_returns_manager(self):
        """get_handoff_manager should return HandoffManager."""
        from src.harness.handoff import get_handoff_manager, HandoffManager

        manager = get_handoff_manager()
        assert isinstance(manager, HandoffManager)

    def test_returns_singleton(self):
        """get_handoff_manager should return same instance."""
        from src.harness.handoff import get_handoff_manager

        manager1 = get_handoff_manager()
        manager2 = get_handoff_manager()
        assert manager1 is manager2
