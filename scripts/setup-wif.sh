#!/bin/bash
#
# Workload Identity Federation (WIF) Setup Script
#
# Purpose: Configure GitHub Actions to authenticate with GCP using OIDC tokens
#          instead of static Service Account keys (more secure)
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Project: project38-483612
#   - Service Account: claude-code-agent@project38-483612.iam.gserviceaccount.com
#   - GitHub Repository: edri2or-commits/project38-or
#
# Usage:
#   bash scripts/setup-wif.sh
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="project38-483612"
SERVICE_ACCOUNT="claude-code-agent@project38-483612.iam.gserviceaccount.com"
POOL_NAME="github-pool"
PROVIDER_NAME="github-provider"
GITHUB_REPO="edri2or-commits/project38-or"
GITHUB_OWNER="edri2or-commits"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  GitHub Actions WIF Setup for GCP${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Step 1: Get project number
echo -e "${YELLOW}[1/6]${NC} Getting project number..."
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
echo -e "${GREEN}✓${NC} Project Number: ${PROJECT_NUMBER}"
echo ""

# Step 2: Enable required APIs
echo -e "${YELLOW}[2/6]${NC} Enabling required APIs..."
gcloud services enable \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  --project="${PROJECT_ID}"
echo -e "${GREEN}✓${NC} APIs enabled"
echo ""

# Step 3: Create Workload Identity Pool
echo -e "${YELLOW}[3/6]${NC} Creating Workload Identity Pool..."
if gcloud iam workload-identity-pools describe "${POOL_NAME}" \
  --project="${PROJECT_ID}" \
  --location="global" &>/dev/null; then
  echo -e "${YELLOW}⚠${NC}  Pool '${POOL_NAME}' already exists, skipping..."
else
  gcloud iam workload-identity-pools create "${POOL_NAME}" \
    --project="${PROJECT_ID}" \
    --location="global" \
    --display-name="GitHub Actions Pool"
  echo -e "${GREEN}✓${NC} Workload Identity Pool created"
fi
echo ""

# Step 4: Create OIDC Provider
echo -e "${YELLOW}[4/6]${NC} Creating OIDC Provider..."
if gcloud iam workload-identity-pools providers describe "${PROVIDER_NAME}" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --workload-identity-pool="${POOL_NAME}" &>/dev/null; then
  echo -e "${YELLOW}⚠${NC}  Provider '${PROVIDER_NAME}' already exists, skipping..."
else
  gcloud iam workload-identity-pools providers create-oidc "${PROVIDER_NAME}" \
    --project="${PROJECT_ID}" \
    --location="global" \
    --workload-identity-pool="${POOL_NAME}" \
    --display-name="GitHub Provider" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
    --attribute-condition="assertion.repository_owner == '${GITHUB_OWNER}'" \
    --issuer-uri="https://token.actions.githubusercontent.com"
  echo -e "${GREEN}✓${NC} OIDC Provider created"
fi
echo ""

# Step 5: Grant Service Account Impersonation
echo -e "${YELLOW}[5/6]${NC} Granting Service Account impersonation rights..."
gcloud iam service-accounts add-iam-policy-binding \
  "${SERVICE_ACCOUNT}" \
  --project="${PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/attribute.repository/${GITHUB_REPO}"
echo -e "${GREEN}✓${NC} Impersonation rights granted"
echo ""

# Step 6: Get Provider Resource Name
echo -e "${YELLOW}[6/6]${NC} Retrieving Provider Resource Name..."
PROVIDER_RESOURCE_NAME=$(gcloud iam workload-identity-pools providers describe "${PROVIDER_NAME}" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --workload-identity-pool="${POOL_NAME}" \
  --format="value(name)")
echo ""

# Success summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✓ WIF Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Provider Resource Name:"
echo -e "${BLUE}${PROVIDER_RESOURCE_NAME}${NC}"
echo ""
echo -e "Next steps:"
echo -e "1. Add this to your GitHub Actions workflow:"
echo -e "   ${YELLOW}permissions:${NC}"
echo -e "   ${YELLOW}  id-token: write${NC}"
echo -e "   ${YELLOW}  contents: read${NC}"
echo ""
echo -e "2. Use the google-github-actions/auth action:"
echo -e "   ${YELLOW}- uses: google-github-actions/auth@v2${NC}"
echo -e "   ${YELLOW}  with:${NC}"
echo -e "   ${YELLOW}    workload_identity_provider: '${PROVIDER_RESOURCE_NAME}'${NC}"
echo -e "   ${YELLOW}    service_account: '${SERVICE_ACCOUNT}'${NC}"
echo ""
echo -e "3. No Service Account key needed - GitHub will use OIDC tokens!"
echo ""
