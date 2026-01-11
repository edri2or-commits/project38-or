"""Agent Factory - Natural Language to Working Python Agent.

This module implements Phase 3.2 of the Agent Platform.
It converts natural language descriptions into working Python agents
using Claude Sonnet 4.5 and validates them through the Ralph Wiggum Loop.
"""

from src.factory.generator import generate_agent_code
from src.factory.ralph_loop import ralph_wiggum_loop
from src.factory.validator import validate_code

__all__ = [
    "generate_agent_code",
    "validate_code",
    "ralph_wiggum_loop",
]
