"""Project38-OR - GCP Secret Manager Integration."""

from .secrets_manager import SecretManager, get_secret

__all__ = ["SecretManager", "get_secret"]
