"""Tests for src/harness/resources.py - Resource Management."""

import pytest
from unittest.mock import MagicMock, patch
import asyncio

# Skip all tests if dependencies not installed
pytest.importorskip("psutil")


class TestResourceLimits:
    """Tests for ResourceLimits dataclass."""

    def test_default_values(self):
        """ResourceLimits should have sensible defaults."""
        from src.harness.resources import ResourceLimits

        limits = ResourceLimits()
        assert limits.max_concurrent_agents == 5
        assert limits.max_memory_mb == 256
        assert limits.max_cpu_percent == 50.0
        assert limits.memory_warning_threshold == 80.0
        assert limits.cpu_warning_threshold == 75.0

    def test_custom_values(self):
        """ResourceLimits should accept custom values."""
        from src.harness.resources import ResourceLimits

        limits = ResourceLimits(
            max_concurrent_agents=10,
            max_memory_mb=512,
            max_cpu_percent=80.0,
            memory_warning_threshold=90.0,
            cpu_warning_threshold=85.0,
        )
        assert limits.max_concurrent_agents == 10
        assert limits.max_memory_mb == 512
        assert limits.max_cpu_percent == 80.0
        assert limits.memory_warning_threshold == 90.0
        assert limits.cpu_warning_threshold == 85.0


class TestResourceMonitor:
    """Tests for ResourceMonitor class."""

    def test_init_default_limits(self):
        """ResourceMonitor should use default limits."""
        from src.harness.resources import ResourceMonitor, ResourceLimits

        monitor = ResourceMonitor()
        assert monitor.limits.max_concurrent_agents == ResourceLimits().max_concurrent_agents

    def test_init_custom_limits(self):
        """ResourceMonitor should accept custom limits."""
        from src.harness.resources import ResourceMonitor, ResourceLimits

        limits = ResourceLimits(max_concurrent_agents=20)
        monitor = ResourceMonitor(limits)
        assert monitor.limits.max_concurrent_agents == 20

    def test_semaphore_initialized(self):
        """ResourceMonitor should initialize semaphore."""
        from src.harness.resources import ResourceMonitor, ResourceLimits

        limits = ResourceLimits(max_concurrent_agents=3)
        monitor = ResourceMonitor(limits)
        assert monitor.semaphore._value == 3

    @pytest.mark.asyncio
    async def test_check_resources_returns_dict(self):
        """check_resources should return resource dictionary."""
        from src.harness.resources import ResourceMonitor

        monitor = ResourceMonitor()
        resources = await monitor.check_resources()

        assert "memory_percent" in resources
        assert "memory_available_mb" in resources
        assert "cpu_percent" in resources

    @pytest.mark.asyncio
    async def test_check_resources_valid_values(self):
        """check_resources should return valid values."""
        from src.harness.resources import ResourceMonitor

        monitor = ResourceMonitor()
        resources = await monitor.check_resources()

        assert 0 <= resources["memory_percent"] <= 100
        assert resources["memory_available_mb"] >= 0
        assert resources["cpu_percent"] >= 0

    @pytest.mark.asyncio
    async def test_acquire_slot_context_manager(self):
        """acquire_slot should work as async context manager."""
        from src.harness.resources import ResourceMonitor, ResourceLimits

        limits = ResourceLimits(max_concurrent_agents=2)
        monitor = ResourceMonitor(limits)

        initial_value = monitor.semaphore._value
        async with monitor.acquire_slot():
            # Inside context, one slot should be used
            assert monitor.semaphore._value == initial_value - 1
        # After context, slot should be released
        assert monitor.semaphore._value == initial_value

    @pytest.mark.asyncio
    async def test_acquire_slot_limits_concurrency(self):
        """acquire_slot should limit concurrent executions."""
        from src.harness.resources import ResourceMonitor, ResourceLimits

        limits = ResourceLimits(max_concurrent_agents=1)
        monitor = ResourceMonitor(limits)
        results = []

        async def task(id):
            async with monitor.acquire_slot():
                results.append(f"start-{id}")
                await asyncio.sleep(0.1)
                results.append(f"end-{id}")

        # Start two tasks
        await asyncio.gather(task(1), task(2))

        # With max_concurrent=1, tasks should not interleave
        # One task must complete before the other starts
        assert results[0].startswith("start")
        assert results[1].startswith("end")

    @pytest.mark.asyncio
    async def test_get_process_info(self):
        """get_process_info should return process stats."""
        from src.harness.resources import ResourceMonitor
        import os

        monitor = ResourceMonitor()
        pid = os.getpid()
        info = await monitor.get_process_info(pid)

        assert "memory_mb" in info
        assert "memory_percent" in info
        assert "cpu_percent" in info
        assert info["memory_mb"] > 0

    @pytest.mark.asyncio
    async def test_get_process_info_invalid_pid(self):
        """get_process_info should raise for invalid PID."""
        from src.harness.resources import ResourceMonitor
        import psutil

        monitor = ResourceMonitor()

        with pytest.raises(psutil.NoSuchProcess):
            await monitor.get_process_info(999999999)

    def test_is_resource_available_with_slots(self):
        """is_resource_available should return True when slots available."""
        from src.harness.resources import ResourceMonitor, ResourceLimits

        limits = ResourceLimits(max_concurrent_agents=5)
        monitor = ResourceMonitor(limits)

        # Mock psutil to return low usage
        with patch("psutil.virtual_memory") as mock_mem:
            mock_mem.return_value = MagicMock(available=1024 * 1024 * 1024)  # 1GB
            with patch("psutil.cpu_percent", return_value=50.0):
                result = monitor.is_resource_available()

        assert result is True

    def test_is_resource_available_no_slots(self):
        """is_resource_available should return False when no slots."""
        from src.harness.resources import ResourceMonitor, ResourceLimits

        limits = ResourceLimits(max_concurrent_agents=1)
        monitor = ResourceMonitor(limits)

        # Manually deplete semaphore
        monitor.semaphore._value = 0

        result = monitor.is_resource_available()
        assert result is False

    def test_is_resource_available_low_memory(self):
        """is_resource_available should return False when memory low."""
        from src.harness.resources import ResourceMonitor, ResourceLimits

        limits = ResourceLimits(max_concurrent_agents=5, max_memory_mb=512)
        monitor = ResourceMonitor(limits)

        # Mock psutil to return low memory (less than 2x max_memory_mb)
        with patch("psutil.virtual_memory") as mock_mem:
            mock_mem.return_value = MagicMock(available=100 * 1024 * 1024)  # 100MB
            with patch("psutil.cpu_percent", return_value=50.0):
                result = monitor.is_resource_available()

        assert result is False

    def test_is_resource_available_high_cpu(self):
        """is_resource_available should return False when CPU too high."""
        from src.harness.resources import ResourceMonitor, ResourceLimits

        limits = ResourceLimits(max_concurrent_agents=5)
        monitor = ResourceMonitor(limits)

        with patch("psutil.virtual_memory") as mock_mem:
            mock_mem.return_value = MagicMock(available=1024 * 1024 * 1024)
            with patch("psutil.cpu_percent", return_value=95.0):  # > 90%
                result = monitor.is_resource_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_resources_available(self):
        """wait_for_resources should return True when resources available."""
        from src.harness.resources import ResourceMonitor

        monitor = ResourceMonitor()

        with patch.object(monitor, "is_resource_available", return_value=True):
            result = await monitor.wait_for_resources(timeout=5.0)

        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_resources_timeout(self):
        """wait_for_resources should return False on timeout."""
        from src.harness.resources import ResourceMonitor

        monitor = ResourceMonitor()

        with patch.object(monitor, "is_resource_available", return_value=False):
            result = await monitor.wait_for_resources(timeout=0.5)

        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_resources_becomes_available(self):
        """wait_for_resources should return True when resources become available."""
        from src.harness.resources import ResourceMonitor

        monitor = ResourceMonitor()
        call_count = [0]

        def mock_available():
            call_count[0] += 1
            return call_count[0] >= 2  # Available after second call

        with patch.object(monitor, "is_resource_available", side_effect=mock_available):
            result = await monitor.wait_for_resources(timeout=5.0)

        assert result is True


class TestGetResourceMonitor:
    """Tests for get_resource_monitor function."""

    def test_returns_monitor(self):
        """get_resource_monitor should return ResourceMonitor."""
        from src.harness.resources import get_resource_monitor, ResourceMonitor

        monitor = get_resource_monitor()
        assert isinstance(monitor, ResourceMonitor)

    def test_returns_singleton(self):
        """get_resource_monitor should return same instance."""
        from src.harness.resources import get_resource_monitor

        monitor1 = get_resource_monitor()
        monitor2 = get_resource_monitor()
        assert monitor1 is monitor2


class TestSetResourceLimits:
    """Tests for set_resource_limits function."""

    def test_sets_new_limits(self):
        """set_resource_limits should create new monitor with limits."""
        from src.harness.resources import set_resource_limits, get_resource_monitor, ResourceLimits

        limits = ResourceLimits(max_concurrent_agents=15)
        set_resource_limits(limits)

        monitor = get_resource_monitor()
        assert monitor.limits.max_concurrent_agents == 15

    def test_replaces_existing_monitor(self):
        """set_resource_limits should replace existing monitor."""
        from src.harness.resources import set_resource_limits, get_resource_monitor, ResourceLimits

        # Set initial limits
        limits1 = ResourceLimits(max_concurrent_agents=5)
        set_resource_limits(limits1)
        monitor1 = get_resource_monitor()

        # Set new limits
        limits2 = ResourceLimits(max_concurrent_agents=10)
        set_resource_limits(limits2)
        monitor2 = get_resource_monitor()

        # Should be different instances
        assert monitor1 is not monitor2
        assert monitor2.limits.max_concurrent_agents == 10
