"""Observability Module for Project38-OR.

Implements OpenTelemetry instrumentation and metrics collection
for AI agent monitoring (Research Paper #08).
"""

from .metrics import MetricsCollector
from .tracer import get_tracer, instrument_tool

__all__ = ["instrument_tool", "get_tracer", "MetricsCollector"]
