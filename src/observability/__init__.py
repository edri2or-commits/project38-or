"""
Observability Module for Project38-OR

Implements OpenTelemetry instrumentation and metrics collection
for AI agent monitoring (Research Paper #08).
"""

from .tracer import instrument_tool, get_tracer
from .metrics import MetricsCollector

__all__ = ["instrument_tool", "get_tracer", "MetricsCollector"]
