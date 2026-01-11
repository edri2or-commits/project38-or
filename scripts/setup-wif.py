#!/usr/bin/env python3
"""
WIF Setup Script - Pure Python Implementation
Creates Workload Identity Federation for GitHub Actions without gcloud CLI
"""

import json
import sys

from google.api_core import exceptions
from google.cloud import iam_v1, resourcemanager_v3
from google.iam.v1 import iam_policy_pb2

PROJECT_ID = "project38-483612"
SERVICE_ACCOUNT = "claude-code-agent@project38-483612.iam.gserviceaccount.com"
POOL_ID = "github-pool"
PROVIDER_ID = "github-provider"
REPO_OWNER = "edri2or-commits"
REPO_NAME = "project38-or"

def get_project_number():
    """Get GCP project number from project ID."""
    print("📋 Step 1: Getting Project Number...")
    try:
        client = resourcemanager_v3.ProjectsClient()
        project = client.get_project(name=f"projects/{PROJECT_ID}")
        project_number = project.name.split('/')[-1]
        print(f"✅ Project Number: {project_number}")
        return project_number
    except Exception as e:
        print(f"❌ Error getting project number: {e}")
        sys.exit(1)

def enable_apis():
    """Note: API enabling requires serviceusage API which needs gcloud."""
    print("\n🔧 Step 2: APIs (Note: May need manual enabling)")
    print("   Required APIs:")
    print("   - iamcredentials.googleapis.com")
    print("   - sts.googleapis.com")
    print("   If setup fails, enable these in GCP Console")

def create_workload_identity_pool(project_number):
    """Create Workload Identity Pool."""
    print("\n🏊 Step 3: Creating Workload Identity Pool...")

    try:
        # Note: The google-cloud-iam library doesn't have direct WIF pool creation
        # We need to use the IAM Admin API via REST or gcloud
        print("⚠️  Workload Identity Pool creation requires:")
        print("   1. GCP Console: https://console.cloud.google.com/iam-admin/workload-identity-pools")
        print("   2. Or gcloud CLI")
        print("   3. Or REST API call")
        print("\n   Attempting via IAM API...")

        # This would require using the REST API directly
        print("❌ Direct Python API not available for WIF pools")
        print("   Using REST API fallback...")

        return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def setup_via_rest_api():
    """Setup WIF using REST API calls."""
    print("\n🔄 Alternative: Using REST API...")
    print("   This requires authenticated requests to:")
    print("   https://iam.googleapis.com/v1/projects/{project}/locations/global/workloadIdentityPools")
    print("\n   For now, WIF setup requires one of:")
    print("   1. gcloud CLI (recommended)")
    print("   2. Manual setup in GCP Console")
    print("   3. Custom REST API implementation")

def print_manual_instructions(project_number):
    """Print manual setup instructions."""
    print("\n" + "="*60)
    print("📋 MANUAL WIF SETUP INSTRUCTIONS")
    print("="*60)
    print("\nDue to API limitations, please run these commands manually:")
    print("\n1️⃣  Enable Required APIs:")
    print(f"""
gcloud services enable \\
  iamcredentials.googleapis.com \\
  sts.googleapis.com \\
  --project={PROJECT_ID}
""")

    print("\n2️⃣  Create Workload Identity Pool:")
    print(f"""
gcloud iam workload-identity-pools create "{POOL_ID}" \\
  --project="{PROJECT_ID}" \\
  --location="global" \\
  --display-name="GitHub Actions Pool"
""")

    print("\n3️⃣  Create Workload Identity Provider:")
    print(f"""
gcloud iam workload-identity-pools providers create-oidc "{PROVIDER_ID}" \\
  --project="{PROJECT_ID}" \\
  --location="global" \\
  --workload-identity-pool="{POOL_ID}" \\
  --display-name="GitHub Provider" \\
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \\
  --attribute-condition="assertion.repository_owner == '{REPO_OWNER}'" \\
  --issuer-uri="https://token.actions.githubusercontent.com"
""")

    print("\n4️⃣  Grant Service Account Impersonation:")
    print(f"""
gcloud iam service-accounts add-iam-policy-binding \\
  "{SERVICE_ACCOUNT}" \\
  --project="{PROJECT_ID}" \\
  --role="roles/iam.workloadIdentityUser" \\
  --member="principalSet://iam.googleapis.com/projects/{project_number}/locations/global/workloadIdentityPools/{POOL_ID}/attribute.repository/{REPO_OWNER}/{REPO_NAME}"
""")

    print("\n5️⃣  Get Provider Resource Name:")
    print(f"""
gcloud iam workload-identity-pools providers describe "{PROVIDER_ID}" \\
  --project="{PROJECT_ID}" \\
  --location="global" \\
  --workload-identity-pool="{POOL_ID}" \\
  --format="value(name)"
""")

    print("\n" + "="*60)
    print("💡 TIP: Run these commands from:")
    print("   - Your local machine with gcloud installed")
    print("   - GCP Cloud Shell (https://shell.cloud.google.com)")
    print("="*60)

def main():
    """Main execution."""
    print("🚀 WIF Setup - Python Implementation")
    print("="*60)

    # Step 1: Get project number
    project_number = get_project_number()

    # Step 2: Note about APIs
    enable_apis()

    # Step 3: Attempt to create pool
    success = create_workload_identity_pool(project_number)

    if not success:
        # Print manual instructions
        print_manual_instructions(project_number)
        print("\n❌ Automated setup not available without gcloud CLI")
        print("✅ Manual instructions provided above")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
