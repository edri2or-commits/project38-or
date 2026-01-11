"""Resource Management - Monitor and limit agent resource usage.

This module provides resource monitoring and limits for agent execution:
- Memory usage tracking
- CPU throttling
- Process limits
- Resource exhaustion detection
"""

import logging
from dataclasses import dataclass
from typing import Any

import psutil

logger = logging.getLogger(__name__)


@dataclass
class ResourceLimits:
    """Resource limits for agent execution.

    Attributes:
        max_memory_mb: Maximum memory usage in MB
        max_cpu_percent: Maximum CPU usage percentage (0-100)
        max_processes: Maximum number of child processes
    """

    max_memory_mb: int = 256
    max_cpu_percent: float = 80.0
    max_processes: int = 5


class ResourceManager:
    """Monitor and enforce resource limits for agents.

    This manager tracks resource usage and can terminate agents
    that exceed limits.

    Example:
        >>> manager = ResourceManager()
        >>> limits = ResourceLimits(max_memory_mb=128)
        >>> usage = manager.get_process_usage(process_id)
        >>> if manager.exceeds_limits(usage, limits):
        ...     print("Resource limit exceeded")
    """

    def __init__(self):
        """Initialize resource manager."""
        pass

    def get_process_usage(self, process_id: int) -> dict[str, Any]:
        """Get current resource usage for a process.

        Args:
            process_id: Process ID to monitor

        Returns:
            Dict with usage metrics:
                - memory_mb: Memory usage in MB
                - cpu_percent: CPU usage percentage
                - num_threads: Number of threads
                - num_children: Number of child processes

        Raises:
            ValueError: If process not found
        """
        try:
            process = psutil.Process(process_id)

            # Get memory info
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)  # Convert bytes to MB

            # Get CPU percent (requires short interval)
            cpu_percent = process.cpu_percent(interval=0.1)

            # Get thread and process counts
            num_threads = process.num_threads()
            children = process.children(recursive=True)
            num_children = len(children)

            return {
                "memory_mb": memory_mb,
                "cpu_percent": cpu_percent,
                "num_threads": num_threads,
                "num_children": num_children,
            }

        except psutil.NoSuchProcess:
            raise ValueError(f"Process {process_id} not found")

    def exceeds_limits(
        self,
        usage: dict[str, Any],
        limits: ResourceLimits,
    ) -> bool:
        """Check if resource usage exceeds limits.

        Args:
            usage: Usage metrics from get_process_usage()
            limits: Resource limits to enforce

        Returns:
            True if any limit exceeded
        """
        if usage["memory_mb"] > limits.max_memory_mb:
            logger.warning(
                f"Memory limit exceeded: {usage['memory_mb']:.2f}MB > "
                f"{limits.max_memory_mb}MB"
            )
            return True

        if usage["cpu_percent"] > limits.max_cpu_percent:
            logger.warning(
                f"CPU limit exceeded: {usage['cpu_percent']:.2f}% > "
                f"{limits.max_cpu_percent}%"
            )
            return True

        if usage["num_children"] > limits.max_processes:
            logger.warning(
                f"Process limit exceeded: {usage['num_children']} > "
                f"{limits.max_processes}"
            )
            return True

        return False

    def get_system_resources(self) -> dict[str, Any]:
        """Get overall system resource availability.

        Returns:
            Dict with system metrics:
                - total_memory_mb: Total system memory in MB
                - available_memory_mb: Available memory in MB
                - memory_percent: Memory usage percentage
                - cpu_count: Number of CPU cores
                - cpu_percent: Overall CPU usage percentage
        """
        # Memory stats
        memory = psutil.virtual_memory()
        total_memory_mb = memory.total / (1024 * 1024)
        available_memory_mb = memory.available / (1024 * 1024)
        memory_percent = memory.percent

        # CPU stats
        cpu_count = psutil.cpu_count()
        cpu_percent = psutil.cpu_percent(interval=0.1)

        return {
            "total_memory_mb": total_memory_mb,
            "available_memory_mb": available_memory_mb,
            "memory_percent": memory_percent,
            "cpu_count": cpu_count,
            "cpu_percent": cpu_percent,
        }

    def kill_process(self, process_id: int, force: bool = False) -> None:
        """Terminate a process.

        Args:
            process_id: Process ID to terminate
            force: If True, use SIGKILL instead of SIGTERM

        Raises:
            ValueError: If process not found
        """
        try:
            process = psutil.Process(process_id)

            if force:
                process.kill()  # SIGKILL
                logger.info(f"Force killed process {process_id}")
            else:
                process.terminate()  # SIGTERM
                logger.info(f"Terminated process {process_id}")

        except psutil.NoSuchProcess:
            raise ValueError(f"Process {process_id} not found")
