# Workload Identity Federation (WIF) Setup Script (PowerShell)
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
#   .\scripts\setup-wif.ps1
#

param(
    [string]$ProjectId = "project38-483612",
    [string]$ServiceAccount = "claude-code-agent@project38-483612.iam.gserviceaccount.com",
    [string]$PoolName = "github-pool",
    [string]$ProviderName = "github-provider",
    [string]$GitHubRepo = "edri2or-commits/project38-or",
    [string]$GitHubOwner = "edri2or-commits"
)

$ErrorActionPreference = "Continue"

# Colors
function Write-ColorOutput($ForegroundColor, $Message) {
    Write-Host $Message -ForegroundColor $ForegroundColor
}

Write-ColorOutput Cyan "========================================"
Write-ColorOutput Cyan "  GitHub Actions WIF Setup for GCP"
Write-ColorOutput Cyan "========================================"
Write-Host ""

# Check if gcloud is installed
try {
    $gcloudVersion = gcloud --version 2>&1 | Select-Object -First 1
    Write-ColorOutput Green "OK gcloud CLI found: $gcloudVersion"
} catch {
    Write-ColorOutput Red "ERROR gcloud CLI not found"
    Write-Host "Please install from: https://cloud.google.com/sdk/docs/install"
    exit 1
}
Write-Host ""

# Step 1: Get project number
Write-ColorOutput Yellow "[1/6] Getting project number..."
$ProjectNumber = gcloud projects describe $ProjectId --format="value(projectNumber)"
Write-ColorOutput Green "OK Project Number: $ProjectNumber"
Write-Host ""

# Step 2: Enable required APIs
Write-ColorOutput Yellow "[2/6] Enabling required APIs..."
gcloud services enable iamcredentials.googleapis.com sts.googleapis.com --project=$ProjectId
Write-ColorOutput Green "OK APIs enabled"
Write-Host ""

# Step 3: Create Workload Identity Pool
Write-ColorOutput Yellow "[3/6] Creating Workload Identity Pool..."
$poolCheck = gcloud iam workload-identity-pools describe $PoolName --project=$ProjectId --location="global" 2>$null
if ($poolCheck) {
    Write-ColorOutput Yellow "WARNING Pool '$PoolName' already exists, skipping..."
} else {
    Write-Host "Creating new pool..."
    gcloud iam workload-identity-pools create $PoolName --project=$ProjectId --location="global" --display-name="GitHub Actions Pool"
    if ($LASTEXITCODE -eq 0) {
        Write-ColorOutput Green "OK Workload Identity Pool created"
    } else {
        Write-ColorOutput Red "ERROR Failed to create pool"
        exit 1
    }
}
Write-Host ""

# Step 4: Create OIDC Provider
Write-ColorOutput Yellow "[4/6] Creating OIDC Provider..."
$providerCheck = gcloud iam workload-identity-pools providers describe $ProviderName --project=$ProjectId --location="global" --workload-identity-pool=$PoolName 2>$null
if ($providerCheck) {
    Write-ColorOutput Yellow "WARNING Provider '$ProviderName' already exists, skipping..."
} else {
    Write-Host "Creating new provider..."
    gcloud iam workload-identity-pools providers create-oidc $ProviderName --project=$ProjectId --location="global" --workload-identity-pool=$PoolName --display-name="GitHub Provider" --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" --attribute-condition="assertion.repository_owner == '$GitHubOwner'" --issuer-uri="https://token.actions.githubusercontent.com"
    if ($LASTEXITCODE -eq 0) {
        Write-ColorOutput Green "OK OIDC Provider created"
    } else {
        Write-ColorOutput Red "ERROR Failed to create provider"
        exit 1
    }
}
Write-Host ""

# Step 5: Grant Service Account Impersonation
Write-ColorOutput Yellow "[5/6] Granting Service Account impersonation rights..."
$memberValue = "principalSet://iam.googleapis.com/projects/$ProjectNumber/locations/global/workloadIdentityPools/$PoolName/attribute.repository/$GitHubRepo"
gcloud iam service-accounts add-iam-policy-binding $ServiceAccount --project=$ProjectId --role="roles/iam.workloadIdentityUser" --member=$memberValue
Write-ColorOutput Green "OK Impersonation rights granted"
Write-Host ""

# Step 6: Get Provider Resource Name
Write-ColorOutput Yellow "[6/6] Retrieving Provider Resource Name..."
$ProviderResourceName = gcloud iam workload-identity-pools providers describe $ProviderName --project=$ProjectId --location="global" --workload-identity-pool=$PoolName --format="value(name)"
Write-Host ""

# Success summary
Write-ColorOutput Green "========================================"
Write-ColorOutput Green "  OK WIF Setup Complete!"
Write-ColorOutput Green "========================================"
Write-Host ""
Write-Host "Provider Resource Name:"
Write-ColorOutput Cyan $ProviderResourceName
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Add this to your GitHub Actions workflow:"
Write-ColorOutput Yellow "   permissions:"
Write-ColorOutput Yellow "     id-token: write"
Write-ColorOutput Yellow "     contents: read"
Write-Host ""
Write-Host "2. Use the google-github-actions/auth action:"
Write-ColorOutput Yellow "   - uses: google-github-actions/auth@v2"
Write-ColorOutput Yellow "     with:"
Write-ColorOutput Yellow "       workload_identity_provider: '$ProviderResourceName'"
Write-ColorOutput Yellow "       service_account: '$ServiceAccount'"
Write-Host ""
Write-Host "3. No Service Account key needed!"
Write-Host ""
