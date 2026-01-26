"""Resource Management - Memory, CPU limits and monitoring.

Prevents agent execution from consuming excessive resources using
psutil monitoring and asyncio semaphores for concurrency control.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass

import psutil

logger = logging.getLogger(__name__)


@dataclass
class ResourceLimits:
    """Configuration for agent resource limits.

    Attributes:
        max_concurrent_agents: Maximum number of agents running simultaneously
        max_memory_mb: Maximum memory per agent in megabytes
        max_cpu_percent: Maximum CPU usage per agent (0-100)
        memory_warning_threshold: Log warning when system memory exceeds %
        cpu_warning_threshold: Log warning when system CPU exceeds %
    """

    max_concurrent_agents: int = 5
    max_memory_mb: int = 256
    max_cpu_percent: float = 50.0
    memory_warning_threshold: float = 80.0
    cpu_warning_threshold: float = 75.0


class ResourceMonitor:
    """Monitor system resources and enforce limits.

    Uses psutil to track memory and CPU usage. Provides semaphore-based
    concurrency control to prevent resource exhaustion.

    Attributes:
        limits: ResourceLimits configuration
        semaphore: Asyncio semaphore for concurrency control
    """

    def __init__(self, limits: ResourceLimits | None = None):
        """Initialize resource monitor.

        Args:
            limits: ResourceLimits instance (defaults to standard limits)

        Example:
            >>> monitor = ResourceMonitor()
            >>> await monitor.check_resources()
        """
        self.limits = limits or ResourceLimits()
        self.semaphore = asyncio.Semaphore(self.limits.max_concurrent_agents)
        logger.info(
            "ResourceMonitor initialized (max_concurrent: %d, max_memory: %dMB)",
            self.limits.max_concurrent_agents,
            self.limits.max_memory_mb,
        )

    async def check_resources(self) -> dict[str, float]:
        """Check current system resource usage.

        Returns:
            Dict with memory_percent, memory_available_mb, cpu_percent

        Example:
            >>> resources = await monitor.check_resources()
            >>> print(resources['memory_percent'])
            42.5
        """
        # Get memory stats
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_available_mb = memory.available / (1024 * 1024)

        # Get CPU stats (0.1 second interval for accurate reading)
        cpu_percent = psutil.cpu_percent(interval=0.1)

        # Log warnings if thresholds exceeded
        if memory_percent > self.limits.memory_warning_threshold:
            logger.warning(
                "High memory usage: %.1f%% (threshold: %.1f%%)",
                memory_percent,
                self.limits.memory_warning_threshold,
            )

        if cpu_percent > self.limits.cpu_warning_threshold:
            logger.warning(
                "High CPU usage: %.1f%% (threshold: %.1f%%)",
                cpu_percent,
                self.limits.cpu_warning_threshold,
            )

        return {
            "memory_percent": memory_percent,
            "memory_available_mb": memory_available_mb,
            "cpu_percent": cpu_percent,
        }

    @asynccontextmanager
    async def acquire_slot(self):
        """Acquire execution slot (semaphore) for agent.

        Blocks if max concurrent agents are already running. Use with
        async context manager to ensure release.

        Yields:
            None when slot is acquired and released on exit

        Example:
            >>> async with monitor.acquire_slot():
            ...     await execute_agent(agent_id)
        """
        logger.debug("Acquiring execution slot")
        await self.semaphore.acquire()
        logger.debug(
            "Execution slot acquired (%d available)",
            self.semaphore._value,
        )
        try:
            yield
        finally:
            self.semaphore.release()
            logger.debug(
                "Execution slot released (%d available)",
                self.semaphore._value,
            )

    async def get_process_info(self, pid: int) -> dict[str, float]:
        """Get resource usage for specific process.

        Args:
            pid: Process ID to monitor

        Returns:
            Dict with memory_mb, memory_percent, cpu_percent

        Raises:
            psutil.NoSuchProcess: If process doesn't exist

        Example:
            >>> info = await monitor.get_process_info(12345)
            >>> print(info['memory_mb'])
            128.5
        """
        try:
            process = psutil.Process(pid)

            # Get memory info
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)

            # Get CPU usage (0.1 second interval)
            cpu_percent = process.cpu_percent(interval=0.1)

            # Get memory percentage of total system memory
            memory_percent = process.memory_percent()

            return {
                "memory_mb": memory_mb,
                "memory_percent": memory_percent,
                "cpu_percent": cpu_percent,
            }

        except psutil.NoSuchProcess:
            logger.warning("Process %d no longer exists", pid)
            raise

    def is_resource_available(self) -> bool:
        """Check if resources are available for new agent execution.

        Returns:
            True if system has sufficient resources, False otherwise

        Example:
            >>> if monitor.is_resource_available():
            ...     await execute_agent()
        """
        # Check if semaphore has available slots
        if self.semaphore._value <= 0:
            logger.warning("No execution slots available")
            return False

        # Check system memory
        memory = psutil.virtual_memory()
        memory_available_mb = memory.available / (1024 * 1024)

        if memory_available_mb < self.limits.max_memory_mb * 2:
            logger.warning(
                "Insufficient memory available: %.1fMB (need at least %dMB)",
                memory_available_mb,
                self.limits.max_memory_mb * 2,
            )
            return False

        # Check CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        if cpu_percent > 90.0:
            logger.warning(
                "CPU usage too high: %.1f%% (threshold: 90%%)",
                cpu_percent,
            )
            return False

        return True

    async def wait_for_resources(self, timeout: float = 60.0) -> bool:
        """Wait for resources to become available.

        Polls resource availability until resources are free or timeout.

        Args:
            timeout: Maximum seconds to wait (default: 60)

        Returns:
            True if resources became available, False if timed out

        Example:
            >>> if await monitor.wait_for_resources(timeout=30):
            ...     await execute_agent()
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            if self.is_resource_available():
                return True

            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                logger.warning("Resource wait timed out after %.1fs", elapsed)
                return False

            # Wait before checking again
            await asyncio.sleep(1.0)


# Global resource monitor instance
_global_monitor: ResourceMonitor | None = None


def get_resource_monitor() -> ResourceMonitor:
    """Get global ResourceMonitor singleton.

    Returns:
        Global ResourceMonitor instance

    Example:
        >>> monitor = get_resource_monitor()
        >>> resources = await monitor.check_resources()
    """
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = ResourceMonitor()
    return _global_monitor


def set_resource_limits(limits: ResourceLimits) -> None:
    """Set resource limits for global monitor.

    Args:
        limits: New ResourceLimits configuration

    Example:
        >>> limits = ResourceLimits(max_concurrent_agents=10)
        >>> set_resource_limits(limits)
    """
    global _global_monitor
    _global_monitor = ResourceMonitor(limits)
    logger.info("Resource limits updated: %s", limits)
