"""Night Watch - Autonomous overnight operations.

This module provides the Night Watch system that performs
autonomous operations during night hours and generates
morning summaries.

Implements ADR-013: Night Watch Autonomous Operations.
"""

from src.nightwatch.service import NightWatchService, get_night_watch

__all__ = [
    "NightWatchService",
    "get_night_watch",
]
