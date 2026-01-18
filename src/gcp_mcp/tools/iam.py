"""
IAM tools.

Provides Identity and Access Management capabilities.
"""

import os

try:
    from google.cloud import iam_admin_v1, resourcemanager_v3

    IAM_AVAILABLE = True
except ImportError:
    IAM_AVAILABLE = False


async def list_service_accounts() -> dict:
    """
    List service accounts in the project.

    Returns:
        dict with list of service accounts
    """
    if not IAM_AVAILABLE:
        return {
            "status": "error",
            "error": "google-cloud-iam not installed",
        }

    try:
        project_id = os.getenv("GCP_PROJECT_ID", "project38-483612")
        client = iam_admin_v1.IAMClient()

        project_name = f"projects/{project_id}"
        accounts = []

        for account in client.list_service_accounts(request={"name": project_name}):
            accounts.append(
                {
                    "email": account.email,
                    "display_name": account.display_name,
                    "unique_id": account.unique_id,
                }
            )

        return {
            "status": "success",
            "count": len(accounts),
            "service_accounts": accounts,
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


async def get_iam_policy(resource: str) -> dict:
    """
    Get IAM policy for a resource.

    Args:
        resource: Resource name (e.g., project ID)

    Returns:
        dict with IAM policy bindings
    """
    if not IAM_AVAILABLE:
        return {
            "status": "error",
            "error": "google-cloud-resource-manager not installed",
        }

    try:
        project_id = resource if resource else os.getenv("GCP_PROJECT_ID", "project38-483612")
        client = resourcemanager_v3.ProjectsClient()

        project_name = f"projects/{project_id}"
        policy = client.get_iam_policy(request={"resource": project_name})

        bindings = []
        for binding in policy.bindings:
            bindings.append(
                {
                    "role": binding.role,
                    "members": list(binding.members),
                }
            )

        return {
            "status": "success",
            "resource": project_id,
            "etag": policy.etag.decode() if policy.etag else None,
            "version": policy.version,
            "bindings": bindings,
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "resource": resource,
        }
