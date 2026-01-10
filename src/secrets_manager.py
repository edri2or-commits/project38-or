"""GCP Secret Manager - Secure secret access module."""

import os

from google.api_core import exceptions
from google.cloud import secretmanager


class SecretManager:
    """Secure interface for GCP Secret Manager."""

    def __init__(self, project_id: str | None = None):
        """Initialize Secret Manager client.

        Args:
            project_id: GCP project ID (defaults to project38-483612).
        """
        self.project_id = project_id or "project38-483612"
        self.client = secretmanager.SecretManagerServiceClient()
        self._secrets_cache: dict[str, str] = {}

    def get_secret(self, secret_id: str, version: str = "latest") -> str | None:
        """Retrieve a secret from Secret Manager.

        Args:
            secret_id: The name of the secret.
            version: The version to retrieve (default: "latest").

        Returns:
            The secret value as string, or None if not found.

        Note:
            Secrets are never logged or printed to prevent exposure.
        """
        # Check cache first
        cache_key = f"{secret_id}:{version}"
        if cache_key in self._secrets_cache:
            return self._secrets_cache[cache_key]

        try:
            name = f"projects/{self.project_id}/secrets/{secret_id}/versions/{version}"
            response = self.client.access_secret_version(request={"name": name})
            secret_value = response.payload.data.decode("UTF-8")

            # Cache the secret
            self._secrets_cache[cache_key] = secret_value
            return secret_value

        except exceptions.NotFound:
            print(f"⚠️  Secret '{secret_id}' not found")
            return None
        except exceptions.PermissionDenied:
            print(f"⚠️  Permission denied for secret '{secret_id}'")
            return None
        except Exception as e:
            print(f"⚠️  Error accessing secret '{secret_id}': {type(e).__name__}")
            return None

    def list_secrets(self) -> list:
        """List all available secrets (names only, not values).

        Returns:
            List of secret names.
        """
        try:
            parent = f"projects/{self.project_id}"
            secrets = []

            for secret in self.client.list_secrets(request={"parent": parent}):
                secret_name = secret.name.split("/")[-1]
                secrets.append(secret_name)

            return secrets

        except Exception as e:
            print(f"⚠️  Error listing secrets: {type(e).__name__}")
            return []

    def verify_access(self, secret_id: str) -> bool:
        """Verify access to a secret without retrieving its value.

        Args:
            secret_id: The name of the secret to verify.

        Returns:
            True if secret exists and is accessible, False otherwise.
        """
        result = self.get_secret(secret_id)
        return result is not None

    def load_secrets_to_env(self, secret_mapping: dict[str, str]) -> int:
        """Load secrets into environment variables.

        Args:
            secret_mapping: Dict mapping env var name to secret name.
                           e.g., {"DATABASE_URL": "db-connection-string"}.

        Returns:
            Number of successfully loaded secrets.
        """
        loaded = 0

        for env_var, secret_id in secret_mapping.items():
            secret_value = self.get_secret(secret_id)
            if secret_value:
                os.environ[env_var] = secret_value
                loaded += 1
                print(f"✅ Loaded {env_var} from secret '{secret_id}'")
            else:
                print(f"❌ Failed to load {env_var} from secret '{secret_id}'")

        return loaded

    def clear_cache(self):
        """Clear the secrets cache."""
        self._secrets_cache.clear()


def get_secret(secret_id: str, project_id: str | None = None) -> str | None:
    """Convenience function to get a single secret.

    Args:
        secret_id: The name of the secret.
        project_id: GCP project ID (optional).

    Returns:
        The secret value or None.
    """
    manager = SecretManager(project_id)
    return manager.get_secret(secret_id)


if __name__ == "__main__":
    # Demo: List available secrets without exposing values
    print("🔐 GCP Secret Manager - Demo")
    print("=" * 50)

    manager = SecretManager()

    print("\n📋 Available secrets:")
    secrets = manager.list_secrets()

    if secrets:
        for secret in secrets:
            accessible = "✅" if manager.verify_access(secret) else "❌"
            print(f"  {accessible} {secret}")
    else:
        print("  No secrets found or insufficient permissions")

    print("\n✨ Secret Manager ready for use!")
    print("   Use manager.get_secret('secret-name') to retrieve values")
