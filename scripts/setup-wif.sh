#!/bin/bash
set -e

# WIF Setup Script for project38-or
# This script sets up Workload Identity Federation for GitHub Actions

PROJECT_ID="project38-483612"
SERVICE_ACCOUNT="claude-code-agent@project38-483612.iam.gserviceaccount.com"
POOL_NAME="github-pool"
PROVIDER_NAME="github-provider"
REPO_OWNER="edri2or-commits"
REPO_NAME="project38-or"

echo "🚀 Starting WIF Setup for $PROJECT_ID"
echo "================================================"

# Step 1: Get Project Number
echo ""
echo "📋 Step 1: Getting Project Number..."
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
echo "✅ Project Number: $PROJECT_NUMBER"

# Step 2: Enable Required APIs
echo ""
echo "🔧 Step 2: Enabling Required APIs..."
gcloud services enable \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  --project="$PROJECT_ID"
echo "✅ APIs enabled"

# Step 3: Create Workload Identity Pool
echo ""
echo "🏊 Step 3: Creating Workload Identity Pool..."
if gcloud iam workload-identity-pools describe "$POOL_NAME" \
  --project="$PROJECT_ID" \
  --location="global" &>/dev/null; then
  echo "⚠️  Pool already exists, skipping..."
else
  gcloud iam workload-identity-pools create "$POOL_NAME" \
    --project="$PROJECT_ID" \
    --location="global" \
    --display-name="GitHub Actions Pool"
  echo "✅ Pool created"
fi

# Step 4: Create Workload Identity Provider
echo ""
echo "🔐 Step 4: Creating Workload Identity Provider..."
if gcloud iam workload-identity-pools providers describe "$PROVIDER_NAME" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_NAME" &>/dev/null; then
  echo "⚠️  Provider already exists, skipping..."
else
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_NAME" \
    --project="$PROJECT_ID" \
    --location="global" \
    --workload-identity-pool="$POOL_NAME" \
    --display-name="GitHub Provider" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
    --attribute-condition="assertion.repository_owner == '$REPO_OWNER'" \
    --issuer-uri="https://token.actions.githubusercontent.com"
  echo "✅ Provider created"
fi

# Step 5: Grant Service Account Impersonation
echo ""
echo "🔑 Step 5: Granting Service Account Impersonation..."
gcloud iam service-accounts add-iam-policy-binding \
  "$SERVICE_ACCOUNT" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL_NAME/attribute.repository/$REPO_OWNER/$REPO_NAME"
echo "✅ IAM binding added"

# Step 6: Get Workload Identity Provider Resource Name
echo ""
echo "📝 Step 6: Getting Provider Resource Name..."
PROVIDER_RESOURCE_NAME=$(gcloud iam workload-identity-pools providers describe "$PROVIDER_NAME" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_NAME" \
  --format="value(name)")
echo "✅ Provider Resource Name: $PROVIDER_RESOURCE_NAME"

# Summary
echo ""
echo "================================================"
echo "🎉 WIF Setup Complete!"
echo "================================================"
echo ""
echo "📋 Configuration Summary:"
echo "  Project ID: $PROJECT_ID"
echo "  Project Number: $PROJECT_NUMBER"
echo "  Service Account: $SERVICE_ACCOUNT"
echo "  Pool: $POOL_NAME"
echo "  Provider: $PROVIDER_NAME"
echo ""
echo "🔧 Use this in GitHub Actions workflows:"
echo "  workload_identity_provider: '$PROVIDER_RESOURCE_NAME'"
echo "  service_account: '$SERVICE_ACCOUNT'"
echo ""
echo "📝 Next steps:"
echo "  1. Update GitHub Actions workflows to use WIF"
echo "  2. Test authentication with test-wif.yml"
echo "  3. Remove GCP_SERVICE_ACCOUNT_KEY secret after verification"
echo ""
