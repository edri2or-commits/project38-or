"""OpenTelemetry Tracer for AI Agents.

Implements OTel GenAI Semantic Conventions v1.37+ as specified in
Research Paper #08, Section 5.1 (Phase 1: Instrumentation).

Usage:
    @instrument_tool("search_knowledge_base")
    async def search(query: str):
        return results
"""

import json
import re
from collections.abc import Callable
from functools import wraps
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Status, StatusCode

# Initialize tracer provider
resource = Resource.create({SERVICE_NAME: "project38-agent"})
provider = TracerProvider(resource=resource)

# For Phase 1: Console exporter (development)
# For Phase 2: OTLP exporter to Collector
console_exporter = ConsoleSpanExporter()
provider.add_span_processor(BatchSpanProcessor(console_exporter))

trace.set_tracer_provider(provider)
tracer = trace.get_tracer("agent.core", "1.0.0")


def get_tracer():
    """Get the global tracer instance."""
    return tracer


def sanitize_pii(data: Any) -> Any:
    """Simple PII redaction helper.

    Redacts common PII patterns:
    - Email addresses
    - Phone numbers
    - SSNs
    - Credit card numbers

    Args:
        data: Input data (dict, str, or Any)

    Returns:
        Sanitized data with PII replaced by [REDACTED]
    """
    if isinstance(data, dict):
        return {k: sanitize_pii(v) for k, v in data.items()}
    elif isinstance(data, str):
        # Email pattern
        data = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                     '[EMAIL_REDACTED]', data)
        # Phone pattern (US)
        data = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE_REDACTED]', data)
        # SSN pattern
        data = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN_REDACTED]', data)
        # Credit card pattern (simple)
        data = re.sub(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
                     '[CC_REDACTED]', data)
        return data
    elif isinstance(data, (list, tuple)):
        return type(data)(sanitize_pii(item) for item in data)
    else:
        return data


def instrument_tool(tool_name: str):
    """Decorator to instrument agent tools with OTel GenAI conventions v1.37+.

    Based on Research Paper #08, Code Snippet (Line 180-223).

    Captures:
    - Tool execution spans
    - Input arguments (sanitized)
    - Output responses (truncated)
    - Success/failure status
    - Execution time (automatic)

    Args:
        tool_name: Name of the tool (e.g., "search_database", "send_email")

    Returns:
        Decorated function with tracing

    Example:
        >>> @instrument_tool("database_query")
        >>> async def query_db(sql: str):
        >>>     return results
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Start a span for the tool execution
            with tracer.start_as_current_span(
                f"tool.execution.{tool_name}",
                kind=trace.SpanKind.INTERNAL
            ) as span:
                # Set Standard GenAI Attributes (v1.37)
                span.set_attribute("gen_ai.system", "project38-agent")
                span.set_attribute("gen_ai.tool.name", tool_name)

                # Capture Input Arguments (Sanitized)
                safe_kwargs = sanitize_pii(kwargs)
                span.set_attribute("gen_ai.tool.args", json.dumps(safe_kwargs))

                try:
                    result = await func(*args, **kwargs)

                    # Capture Success
                    span.set_status(Status(StatusCode.OK))

                    # Capture Output (truncated to prevent bloat)
                    result_str = str(result)
                    if len(result_str) > 1000:
                        result_str = result_str[:1000] + "... [TRUNCATED]"
                    span.set_attribute("gen_ai.tool.response", result_str)

                    return result

                except Exception as e:
                    # Capture Failure
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    raise e

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Same logic for sync functions
            with tracer.start_as_current_span(
                f"tool.execution.{tool_name}",
                kind=trace.SpanKind.INTERNAL
            ) as span:
                span.set_attribute("gen_ai.system", "project38-agent")
                span.set_attribute("gen_ai.tool.name", tool_name)

                safe_kwargs = sanitize_pii(kwargs)
                span.set_attribute("gen_ai.tool.args", json.dumps(safe_kwargs))

                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))

                    result_str = str(result)
                    if len(result_str) > 1000:
                        result_str = result_str[:1000] + "... [TRUNCATED]"
                    span.set_attribute("gen_ai.tool.response", result_str)

                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    raise e

        # Return appropriate wrapper based on function type
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
