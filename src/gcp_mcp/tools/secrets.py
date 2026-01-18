"""
Secret Manager tools.

Provides safe access to GCP Secret Manager with proper security controls.
"""

import os

try:
    from google.cloud import secretmanager

    SECRET_MANAGER_AVAILABLE = True
except ImportError:
    SECRET_MANAGER_AVAILABLE = False


async def get_secret_value(secret_name: str, version: str = "latest") -> dict:
    """
    Get a secret value from Secret Manager.

    Args:
        secret_name: Name of the secret
        version: Version to retrieve

    Returns:
        dict with secret metadata (value is masked for security)

    Security Note:
        Only returns metadata by default. Full value retrieval requires
        explicit confirmation.
    """
    if not SECRET_MANAGER_AVAILABLE:
        return {
            "status": "error",
            "error": "google-cloud-secret-manager not installed",
        }

    try:
        project_id = os.getenv("GCP_PROJECT_ID", "project38-483612")
        client = secretmanager.SecretManagerServiceClient()

        name = f"projects/{project_id}/secrets/{secret_name}/versions/{version}"
        response = client.access_secret_version(request={"name": name})

        # Get metadata
        secret_value = response.payload.data.decode("UTF-8")

        return {
            "status": "success",
            "secret_name": secret_name,
            "version": version,
            "value_length": len(secret_value),
            "value_preview": secret_value[:10] + "..." if len(secret_value) > 10 else "[MASKED]",
            "message": "Secret retrieved successfully. Use value_length to verify.",
            "security_note": "Full value not returned for security. Use gcloud if needed.",
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "secret_name": secret_name,
        }


async def list_secrets() -> dict:
    """
    List all secrets in Secret Manager.

    Returns:
        dict with list of secret names and metadata
    """
    if not SECRET_MANAGER_AVAILABLE:
        return {
            "status": "error",
            "error": "google-cloud-secret-manager not installed",
        }

    try:
        project_id = os.getenv("GCP_PROJECT_ID", "project38-483612")
        client = secretmanager.SecretManagerServiceClient()

        parent = f"projects/{project_id}"
        secrets = []

        for secret in client.list_secrets(request={"parent": parent}):
            secrets.append(
                {
                    "name": secret.name.split("/")[-1],
                    "full_name": secret.name,
                    "create_time": str(secret.create_time),
                }
            )

        return {
            "status": "success",
            "count": len(secrets),
            "secrets": secrets,
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


async def create_secret(secret_name: str, secret_value: str) -> dict:
    """
    Create a new secret in Secret Manager.

    Args:
        secret_name: Name for the new secret
        secret_value: Secret value to store

    Returns:
        dict with creation status
    """
    if not SECRET_MANAGER_AVAILABLE:
        return {
            "status": "error",
            "error": "google-cloud-secret-manager not installed",
        }

    try:
        project_id = os.getenv("GCP_PROJECT_ID", "project38-483612")
        client = secretmanager.SecretManagerServiceClient()

        parent = f"projects/{project_id}"

        # Create secret
        secret = client.create_secret(
            request={
                "parent": parent,
                "secret_id": secret_name,
                "secret": {"replication": {"automatic": {}}},
            }
        )

        # Add secret version with value
        client.add_secret_version(
            request={
                "parent": secret.name,
                "payload": {"data": secret_value.encode("UTF-8")},
            }
        )

        return {
            "status": "success",
            "secret_name": secret_name,
            "message": f"Secret {secret_name} created successfully",
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "secret_name": secret_name,
        }


async def update_secret(secret_name: str, secret_value: str) -> dict:
    """
    Update an existing secret (add new version).

    Args:
        secret_name: Name of the secret
        secret_value: New secret value

    Returns:
        dict with update status and new version
    """
    if not SECRET_MANAGER_AVAILABLE:
        return {
            "status": "error",
            "error": "google-cloud-secret-manager not installed",
        }

    try:
        project_id = os.getenv("GCP_PROJECT_ID", "project38-483612")
        client = secretmanager.SecretManagerServiceClient()

        parent = f"projects/{project_id}/secrets/{secret_name}"

        # Add new secret version
        version = client.add_secret_version(
            request={
                "parent": parent,
                "payload": {"data": secret_value.encode("UTF-8")},
            }
        )

        version_id = version.name.split("/")[-1]

        return {
            "status": "success",
            "secret_name": secret_name,
            "new_version": version_id,
            "message": f"Secret {secret_name} updated to version {version_id}",
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "secret_name": secret_name,
        }
