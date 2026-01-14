"""Project38-OR - GCP Secret Manager Integration.

This package provides autonomous AI agent infrastructure with GCP integration.

Note: Imports are lazy to prevent cascading dependencies during test collection.
Use explicit imports: `from src.secrets_manager import SecretManager`
"""

__all__ = ["SecretManager", "get_secret"]


def __getattr__(name: str):
    """Lazy import to avoid loading Google Cloud SDK at module import time."""
    if name in ("SecretManager", "get_secret"):
        from .secrets_manager import SecretManager, get_secret

        if name == "SecretManager":
            return SecretManager
        return get_secret
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
