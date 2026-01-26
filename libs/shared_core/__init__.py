"""Shared core library - domain-agnostic utilities.

This library provides shared utilities used by both BUSINESS and PERSONAL domains.
It MUST NOT import from apps.business.* or apps.personal.*.

Components:
    - secrets: GCP Secret Manager integration
    - logging: Structured JSON logging

Usage:
    from libs.shared_core.secrets import SecretManager, get_secret
    from libs.shared_core.logging import setup_logging
"""

from libs.shared_core.logging import JSONFormatter, setup_logging
from libs.shared_core.secrets import SecretManager, get_secret

__all__ = [
    "SecretManager",
    "get_secret",
    "setup_logging",
    "JSONFormatter",
]
