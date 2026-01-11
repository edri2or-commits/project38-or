"""Resource management for agent execution.

This module provides monitoring and control of system resources
(memory, CPU) for running agents. It prevents resource exhaustion
by enforcing limits on concurrent executions and per-agent usage.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import psutil

logger = logging.getLogger(__name__)


@dataclass
class ResourceLimits:
    """Resource limits for agent execution.

    Attributes:
        max_memory_mb: Maximum memory per agent in megabytes
        max_cpu_percent: Maximum CPU usage per agent (0-100)
        max_concurrent_agents: Maximum number of concurrent agent executions
        max_execution_time: Maximum execution time in seconds
    """

    max_memory_mb: int = 256
    max_cpu_percent: float = 50.0
    max_concurrent_agents: int = 5
    max_execution_time: int = 300  # 5 minutes


@dataclass
class ResourceUsage:
    """Current resource usage statistics.

    Attributes:
        memory_mb: Current memory usage in megabytes
        memory_percent: Memory usage as percentage of system total
        cpu_percent: CPU usage percentage
        active_agents: Number of currently running agents
    """

    memory_mb: float
    memory_percent: float
    cpu_percent: float
    active_agents: int


class ResourceManager:
    """Manages resource allocation and monitoring for agent execution.

    Tracks system resource usage and enforces limits to prevent
    resource exhaustion. Uses semaphores to limit concurrent executions.

    Attributes:
        limits: Resource limits configuration
        semaphore: Asyncio semaphore for concurrent execution control
        active_agents: Counter of currently running agents
    """

    def __init__(self, limits: Optional[ResourceLimits] = None):
        """Initialize the resource manager.

        Args:
            limits: Resource limits configuration (uses defaults if None)
        """
        self.limits = limits or ResourceLimits()
        self.semaphore = asyncio.Semaphore(self.limits.max_concurrent_agents)
        self.active_agents = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """Acquire resources for agent execution.

        Checks if system has sufficient resources and acquires
        a slot in the execution semaphore.

        Returns:
            bool: True if resources acquired, False if limits exceeded

        Example:
            >>> manager = ResourceManager()
            >>> if await manager.acquire():
            ...     try:
            ...         # Run agent
            ...         pass
            ...     finally:
            ...         await manager.release()
        """
        # Check system resources
        if not self._check_system_resources():
            logger.warning("System resources exhausted, cannot start agent")
            return False

        # Acquire semaphore slot
        try:
            await asyncio.wait_for(
                self.semaphore.acquire(),
                timeout=1.0,  # Don't wait long
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"Max concurrent agents ({self.limits.max_concurrent_agents}) reached"
            )
            return False

        async with self._lock:
            self.active_agents += 1

        return True

    async def release(self):
        """Release resources after agent execution completes.

        Must be called in a finally block to ensure resources are freed.
        """
        self.semaphore.release()
        async with self._lock:
            self.active_agents = max(0, self.active_agents - 1)

    def _check_system_resources(self) -> bool:
        """Check if system has sufficient resources available.

        Returns:
            bool: True if resources available, False if limits exceeded
        """
        try:
            # Check memory
            memory = psutil.virtual_memory()
            available_mb = memory.available / (1024 * 1024)

            if available_mb < self.limits.max_memory_mb * 2:
                logger.warning(
                    f"Low memory: {available_mb:.0f}MB available, "
                    f"need {self.limits.max_memory_mb}MB per agent"
                )
                return False

            # Check CPU
            cpu_percent = psutil.cpu_percent(interval=0.1)
            if cpu_percent > 90.0:
                logger.warning(f"High CPU usage: {cpu_percent:.1f}%")
                return False

            return True

        except Exception as e:
            logger.error(f"Error checking system resources: {e}")
            return False

    def get_usage(self) -> ResourceUsage:
        """Get current resource usage statistics.

        Returns:
            ResourceUsage: Current resource usage

        Example:
            >>> manager = ResourceManager()
            >>> usage = manager.get_usage()
            >>> print(f"Memory: {usage.memory_mb:.0f}MB, CPU: {usage.cpu_percent:.1f}%")
        """
        try:
            memory = psutil.virtual_memory()
            process = psutil.Process()

            return ResourceUsage(
                memory_mb=process.memory_info().rss / (1024 * 1024),
                memory_percent=memory.percent,
                cpu_percent=psutil.cpu_percent(interval=0.1),
                active_agents=self.active_agents,
            )

        except Exception as e:
            logger.error(f"Error getting resource usage: {e}")
            return ResourceUsage(
                memory_mb=0.0,
                memory_percent=0.0,
                cpu_percent=0.0,
                active_agents=self.active_agents,
            )

    def check_limits(self, usage: ResourceUsage) -> tuple[bool, str]:
        """Check if resource usage is within limits.

        Args:
            usage: Current resource usage

        Returns:
            Tuple of (within_limits, violation_message)
                within_limits: True if all limits satisfied
                violation_message: Description of violation if any

        Example:
            >>> manager = ResourceManager()
            >>> usage = manager.get_usage()
            >>> ok, msg = manager.check_limits(usage)
            >>> if not ok:
            ...     print(f"Limit violation: {msg}")
        """
        violations = []

        if usage.memory_percent > 90.0:
            violations.append(f"Memory usage {usage.memory_percent:.1f}% exceeds 90%")

        if usage.cpu_percent > self.limits.max_cpu_percent:
            violations.append(
                f"CPU usage {usage.cpu_percent:.1f}% exceeds limit "
                f"{self.limits.max_cpu_percent:.1f}%"
            )

        if usage.active_agents >= self.limits.max_concurrent_agents:
            violations.append(
                f"Active agents {usage.active_agents} at limit "
                f"{self.limits.max_concurrent_agents}"
            )

        if violations:
            return False, "; ".join(violations)

        return True, ""


# Global resource manager instance
_resource_manager: Optional[ResourceManager] = None


def get_resource_manager(limits: Optional[ResourceLimits] = None) -> ResourceManager:
    """Get or create the global resource manager instance.

    Args:
        limits: Resource limits configuration (ignored if instance exists)

    Returns:
        ResourceManager: The global resource manager

    Example:
        >>> manager = get_resource_manager()
        >>> usage = manager.get_usage()
        >>> print(f"Active agents: {usage.active_agents}")
    """
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager(limits)
    return _resource_manager
