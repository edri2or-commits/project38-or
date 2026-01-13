# Autonomous Architecture & Security Design

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Components](#architecture-components)
3. [Control Flow](#control-flow)
4. [Security Framework](#security-framework)
5. [Token Management](#token-management)
6. [Identity & Access Management](#identity--access-management)
7. [Monitoring & Observability](#monitoring--observability)
8. [Error Handling & Recovery](#error-handling--recovery)
9. [Deployment Architecture](#deployment-architecture)
10. [Security Best Practices](#security-best-practices)

---

## System Overview

### Vision

Build a **fully autonomous Claude AI agent** that manages the entire development lifecycle across Railway, GitHub, and n8n without human intervention, while maintaining enterprise-grade security.

### Core Capabilities

```
┌─────────────────────────────────────────────────────────────┐
│                     Claude Agent (Core)                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │   Planner  │  │  Executor  │  │  Monitor   │            │
│  │  (Claude)  │→ │  (Actions) │→ │ (Observer) │            │
│  └────────────┘  └────────────┘  └────────────┘            │
└──────────────┬──────────────┬──────────────┬────────────────┘
               │              │              │
       ┌───────┴──────┐ ┌─────┴──────┐ ┌────┴──────┐
       │   Railway    │ │   GitHub   │ │    n8n    │
       │   GraphQL    │ │  App Auth  │ │  REST API │
       │     API      │ │   (JWT)    │ │   (API)   │
       └──────────────┘ └────────────┘ └───────────┘
               │              │              │
       ┌───────┴──────────────┴──────────────┴───────┐
       │         GCP Secret Manager (WIF)             │
       │  • RAILWAY-API    • github-app-private-key   │
       │  • N8N-API        • ANTHROPIC-API            │
       └──────────────────────────────────────────────┘
```

### Key Principles

1. **Zero Human Intervention**: Agent operates fully autonomously
2. **Defense in Depth**: Multiple security layers
3. **Least Privilege**: Minimal permissions for each operation
4. **Audit Everything**: Complete logging of all actions
5. **Fail Secure**: System fails to safe state, never exposes secrets
6. **Token Rotation**: Automatic credential rotation
7. **Observability**: Real-time monitoring and alerting

---

## Architecture Components

### Layer 1: Authentication & Secrets

```python
┌─────────────────────────────────────────────┐
│         GCP Secret Manager (Source)         │
│  - Workload Identity Federation (WIF)       │
│  - Zero stored credentials                  │
│  - Automatic rotation                       │
└─────────────────┬───────────────────────────┘
                  │
      ┌───────────┴───────────┐
      │  SecretManager Class  │
      │  (src/secrets_manager.py) │
      └───────────┬───────────┘
                  │
    ┌─────────────┴─────────────┐
    │   Credential Providers     │
    │  ┌──────────────────────┐ │
    │  │ GitHub App Auth      │ │
    │  │ - JWT generation     │ │
    │  │ - Token caching (1h) │ │
    │  └──────────────────────┘ │
    │  ┌──────────────────────┐ │
    │  │ Railway API Token    │ │
    │  │ - Direct bearer      │ │
    │  └──────────────────────┘ │
    │  ┌──────────────────────┐ │
    │  │ n8n API Key          │ │
    │  │ - Header auth        │ │
    │  └──────────────────────┘ │
    └───────────────────────────┘
```

**Key Features:**
- ✅ WIF eliminates need for service account keys
- ✅ Secrets fetched on-demand, never stored to disk
- ✅ Automatic token refresh before expiration
- ✅ Clear secrets from memory after use

### Layer 2: API Clients

```python
┌─────────────────────────────────────────────┐
│           Platform API Clients              │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │  RailwayClient                        │  │
│  │  - GraphQL query builder              │  │
│  │  - Deployment monitoring              │  │
│  │  - Rate limit handling                │  │
│  │  - Rollback capabilities              │  │
│  └──────────────────────────────────────┘  │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │  GitHubAppClient                      │  │
│  │  - JWT authentication                 │  │
│  │  - Installation token caching         │  │
│  │  - Workflow trigger                   │  │
│  │  - PR management                      │  │
│  └──────────────────────────────────────┘  │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │  N8nClient                            │  │
│  │  - Workflow execution                 │  │
│  │  - Export/import (version control)    │  │
│  │  - Execution monitoring               │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

**Design Principles:**
- Type hints for all methods
- Async operations (httpx/asyncio)
- Comprehensive error handling
- Automatic retries with exponential backoff
- Structured logging (no secret leakage)

### Layer 3: Orchestration Engine

```python
┌──────────────────────────────────────────────┐
│         Autonomous Agent Core                │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │  Decision Engine (Claude)              │ │
│  │  - Analyze system state                │ │
│  │  - Plan actions                        │ │
│  │  - Execute via API clients             │ │
│  │  - Validate results                    │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │  State Machine                         │ │
│  │  - Track operation state               │ │
│  │  - Handle failures                     │ │
│  │  - Implement rollback                  │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │  Event Handler                         │ │
│  │  - GitHub webhook receiver             │ │
│  │  - Railway webhook receiver            │ │
│  │  - n8n webhook receiver                │ │
│  └────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

### Layer 4: Observability

```python
┌──────────────────────────────────────────────┐
│            Monitoring & Logging              │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │  Structured Logging                    │ │
│  │  - JSON format                         │ │
│  │  - Correlation IDs                     │ │
│  │  - No secret leakage                   │ │
│  │  - Retention: 30 days                  │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │  Metrics (FastAPI /metrics)            │ │
│  │  - API call counts                     │ │
│  │  - Success/failure rates               │ │
│  │  - Latency percentiles                 │ │
│  │  - Token refresh rates                 │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │  Alerting (Telegram/n8n)               │ │
│  │  - Deployment failures                 │ │
│  │  - API errors                          │ │
│  │  - Token expiration warnings           │ │
│  └────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

---

## Control Flow

### Typical Deployment Flow

```
1. Code Change
   ├─ Developer pushes to feature branch
   └─ GitHub webhook → Claude webhook endpoint

2. Claude Analysis
   ├─ Fetch PR details (GitHubAppClient)
   ├─ Review code changes
   ├─ Run tests via GitHub Actions
   └─ Decision: Deploy or reject

3. Deployment Execution
   ├─ Trigger Railway deployment (RailwayClient)
   ├─ Monitor deployment status (polling)
   ├─ Stream logs for analysis
   └─ Wait for health check

4. Verification
   ├─ Hit /health endpoint on Railway
   ├─ Run smoke tests
   └─ Decision: Keep or rollback

5. Notification
   ├─ Trigger n8n workflow (N8nClient)
   ├─ n8n sends Telegram notification
   └─ Update GitHub PR with status

6. Cleanup
   ├─ Merge PR if successful (GitHubAppClient)
   ├─ Delete feature branch
   └─ Log to observability system
```

### Error Recovery Flow

```
Error Detected
   ├─ Log error with context
   ├─ Determine if recoverable
   │  ├─ Yes → Retry with backoff
   │  └─ No → Initiate rollback
   │
   ├─ Rollback Steps
   │  ├─ Railway: Redeploy previous version
   │  ├─ GitHub: Revert PR if merged
   │  └─ n8n: Send alert workflow
   │
   ├─ Notification
   │  ├─ Send detailed error report
   │  ├─ Include logs and traces
   │  └─ Suggest remediation
   │
   └─ State Recovery
      ├─ Reset to last known good state
      ├─ Clear cached tokens
      └─ Resume normal operations
```

---

## Security Framework

### Threat Model

#### Critical Assets

1. **Secrets**
   - Railway API token
   - GitHub App private key
   - n8n API key
   - Anthropic API key

2. **Infrastructure**
   - Railway production environment
   - GitHub repository (code, workflows)
   - n8n workflows (automation logic)
   - GCP Secret Manager

3. **Data**
   - Deployment logs (may contain sensitive info)
   - API responses
   - User credentials (n8n, Railway)

#### Threat Actors

1. **External Attackers**
   - Goal: Steal secrets, inject malicious code
   - Vectors: API vulnerabilities, MITM attacks

2. **Compromised Dependencies**
   - Goal: Supply chain attack
   - Vectors: Malicious npm/pip packages

3. **Insider Threats** (Low priority - personal project)
   - Goal: Unauthorized access
   - Vectors: Stolen credentials

#### Attack Scenarios

**Scenario 1: Secret Exposure**
- Attacker gains access to GitHub Actions logs
- Mitigation: Never log secrets, use GCP Secret Manager
- Detection: Audit logs, secret usage monitoring

**Scenario 2: Man-in-the-Middle**
- Attacker intercepts API calls to Railway/GitHub
- Mitigation: HTTPS everywhere, certificate pinning
- Detection: TLS errors, unexpected API responses

**Scenario 3: Token Theft**
- Attacker steals cached GitHub installation token
- Mitigation: In-memory only, short expiration (1 hour)
- Detection: Unusual API usage patterns

**Scenario 4: Unauthorized Deployment**
- Attacker triggers malicious Railway deployment
- Mitigation: GitHub Actions restricted to OWNER only
- Detection: Deployment webhooks, audit logs

### Security Controls

#### Preventive Controls

1. **Authentication**
   - ✅ WIF for GCP (no service account keys)
   - ✅ GitHub App with JWT (not PAT)
   - ✅ API keys with expiration
   - ✅ Certificate-based auth where possible

2. **Authorization**
   - ✅ Least privilege permissions
   - ✅ Repository-scoped GitHub App
   - ✅ Railway project-scoped tokens
   - ✅ n8n workflow-level access control

3. **Encryption**
   - ✅ Secrets encrypted at rest (GCP Secret Manager)
   - ✅ TLS 1.3 for all API calls
   - ✅ n8n credentials encryption (N8N_ENCRYPTION_KEY)

4. **Input Validation**
   - ✅ Validate all webhook payloads
   - ✅ Sanitize user input (issue comments)
   - ✅ Type checking (Pydantic models)

#### Detective Controls

1. **Logging**
   - ✅ Structured JSON logs
   - ✅ Correlation IDs for tracing
   - ✅ Log all authentication attempts
   - ✅ Log all deployment operations

2. **Monitoring**
   - ✅ API error rate alerts
   - ✅ Unusual deployment patterns
   - ✅ Token refresh failures
   - ✅ Rate limit monitoring

3. **Audit Logging**
   - ✅ GCP Audit Logs (Secret Manager access)
   - ✅ GitHub Actions logs
   - ✅ Railway deployment history
   - ✅ n8n execution history

#### Responsive Controls

1. **Incident Response**
   - ✅ Automatic rollback on deployment failure
   - ✅ Token revocation procedures
   - ✅ Alert escalation (Telegram)
   - ✅ Manual override capability

2. **Recovery**
   - ✅ Backup GitHub workflows to Git
   - ✅ Backup n8n workflows daily
   - ✅ Railway deployment history
   - ✅ Database backups (PostgreSQL)

---

## Token Management

### Token Lifecycle

```
┌─────────────────────────────────────────────┐
│         Token Lifecycle Management          │
│                                             │
│  1. Generation                              │
│     ├─ GitHub App: JWT → Installation Token │
│     ├─ Railway: Fetch from Secret Manager   │
│     └─ n8n: Fetch from Secret Manager       │
│                                             │
│  2. Caching (In-Memory Only)                │
│     ├─ GitHub: Cache until 5 min before exp │
│     ├─ Railway: No caching (static token)   │
│     └─ n8n: No caching (static token)       │
│                                             │
│  3. Usage                                   │
│     ├─ Add to request headers               │
│     ├─ Never log token value                │
│     └─ Monitor for 401/403 errors           │
│                                             │
│  4. Refresh                                 │
│     ├─ GitHub: Auto-refresh via JWT         │
│     ├─ Railway: Manual rotation (90 days)   │
│     └─ n8n: Manual rotation (90 days)       │
│                                             │
│  5. Revocation                              │
│     ├─ Clear from memory immediately        │
│     ├─ Revoke in platform UI                │
│     └─ Update Secret Manager                │
└─────────────────────────────────────────────┘
```

### Token Rotation Schedule

| Token | Rotation Frequency | Method | Automation |
|-------|-------------------|--------|------------|
| GitHub App Installation | 1 hour (auto) | JWT exchange | ✅ Automatic |
| Railway API | 90 days | Manual regeneration | ❌ Manual |
| n8n API | 90 days | Manual regeneration | ❌ Manual |
| Anthropic API | 90 days | Manual rotation | ❌ Manual |

**Rotation Procedure (Railway/n8n):**

```python
async def rotate_api_token(platform: str, old_secret_name: str, new_token: str):
    """
    Rotate API token in GCP Secret Manager.

    Args:
        platform: "railway" or "n8n"
        old_secret_name: Secret name in GCP (e.g., "RAILWAY-API")
        new_token: New API token from platform

    Steps:
        1. Generate new token in platform UI
        2. Test new token
        3. Add new version to Secret Manager
        4. Wait for agent to pick up new token
        5. Delete old token in platform UI
    """

    # Test new token
    if platform == "railway":
        # Test Railway API
        headers = {"Authorization": f"Bearer {new_token}"}
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://backboard.railway.com/graphql/v2",
                json={"query": "{ me { id } }"},
                headers=headers
            )
            assert response.status_code == 200, "New token invalid"

    # Add new version to Secret Manager
    import subprocess
    subprocess.run([
        "gcloud", "secrets", "versions", "add", old_secret_name,
        "--data-file=-"
    ], input=new_token.encode(), check=True)

    print(f"✓ Rotated {platform} API token")
    print("⚠️ Remember to delete old token in platform UI after verification")
```

### Token Security Best Practices

#### DO:
- ✅ Store tokens in GCP Secret Manager (encrypted at rest)
- ✅ Use short-lived tokens (GitHub: 1 hour)
- ✅ Cache tokens in memory only (never disk)
- ✅ Clear tokens from memory after use
- ✅ Monitor token usage via audit logs
- ✅ Rotate static tokens every 90 days
- ✅ Use separate tokens for dev/staging/prod

#### DON'T:
- ❌ Log token values (even partial)
- ❌ Store tokens in environment variables
- ❌ Commit tokens to Git
- ❌ Share tokens between environments
- ❌ Use tokens with excessive permissions
- ❌ Reuse tokens after suspected compromise

---

## Identity & Access Management

### IAM Framework for Autonomous AI (2026)

Based on Cloud Security Alliance (CSA) Agentic AI IAM framework:

```
┌─────────────────────────────────────────────┐
│      Decentralized Identity (DID)           │
│  Claude Agent Identity: did:claude:agent-1  │
│  - Cryptographically verifiable             │
│  - Independent of platforms                 │
│  - Supports delegation                      │
└─────────────────┬───────────────────────────┘
                  │
      ┌───────────┴───────────┐
      │  Verifiable Credentials │
      │  - GitHub App           │
      │  - Railway Project      │
      │  - n8n Workflows        │
      └───────────┬───────────┘
                  │
    ┌─────────────┴─────────────┐
    │   Zero Trust Principles    │
    │  - Never trust, verify     │
    │  - Least privilege         │
    │  - Continuous validation   │
    └───────────────────────────┘
```

### Agentic Identity Patterns

#### 1. Workload Identity Federation (GCP)

**Current Implementation:**

```python
# No service account keys!
# WIF binds agent to specific GCP resource

# In GitHub Actions:
permissions:
  id-token: write  # Required for WIF

- name: Authenticate to Google Cloud
  uses: google-github-actions/auth@v2
  with:
    workload_identity_provider: 'projects/979429709900/locations/global/workloadIdentityPools/github-pool/providers/github-provider'
    service_account: 'claude-code-agent@project38-483612.iam.gserviceaccount.com'
```

**Benefits:**
- ✅ No long-lived credentials
- ✅ Bound to GitHub repository
- ✅ Automatic token exchange
- ✅ Audit trail via Cloud IAM

#### 2. Just-In-Time (JIT) Permissions

**Concept:** Grant permissions only for specific task duration

**Example Implementation:**

```python
from datetime import datetime, timedelta

class JITPermissionManager:
    """Grant temporary elevated permissions for specific operations."""

    async def with_elevated_permissions(
        self,
        operation: str,
        duration_minutes: int = 15
    ):
        """
        Context manager for temporary permission elevation.

        Example:
            >>> async with jit.with_elevated_permissions("deploy", 15):
            ...     await railway_client.trigger_deployment(...)
        """

        # Log permission elevation
        logger.warning(
            f"Elevated permissions for '{operation}' "
            f"(expires in {duration_minutes} minutes)"
        )

        # Set expiration
        expires_at = datetime.utcnow() + timedelta(minutes=duration_minutes)

        try:
            yield  # Execute operation

        finally:
            # Revoke elevated permissions
            logger.info(f"Revoked elevated permissions for '{operation}'")

            # Clear cached tokens
            await self._clear_token_cache()
```

#### 3. Delegation Patterns

**Use Case:** Claude delegates specific tasks to n8n workflows

```python
class DelegationManager:
    """Manage task delegation to n8n workflows."""

    async def delegate_to_n8n(
        self,
        task: str,
        workflow_id: str,
        inputs: dict,
        constraints: dict
    ):
        """
        Delegate task to n8n workflow with constraints.

        Args:
            task: Task description (for audit)
            workflow_id: n8n workflow ID
            inputs: Task inputs
            constraints: Time limit, retry count, etc.

        Example:
            >>> await delegation.delegate_to_n8n(
            ...     task="Send deployment notification",
            ...     workflow_id="notify-deploy",
            ...     inputs={"status": "success"},
            ...     constraints={"timeout": 60, "retries": 3}
            ... )
        """

        # Log delegation
        logger.info(
            f"Delegating task '{task}' to n8n workflow {workflow_id}",
            extra={
                "task": task,
                "workflow_id": workflow_id,
                "constraints": constraints
            }
        )

        # Execute with constraints
        try:
            result = await asyncio.wait_for(
                self.n8n_client.execute_and_wait(workflow_id, inputs),
                timeout=constraints.get("timeout", 300)
            )

            logger.info(f"Task '{task}' completed successfully")
            return result

        except asyncio.TimeoutError:
            logger.error(f"Task '{task}' timed out")
            raise

        except Exception as e:
            logger.error(f"Task '{task}' failed: {e}")
            raise
```

---

## Monitoring & Observability

### Metrics to Track

#### System Health

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| API Success Rate | > 99% | < 95% |
| Deployment Success Rate | > 95% | < 90% |
| Average Deployment Time | < 3 min | > 5 min |
| Token Refresh Success | 100% | < 100% |
| Health Check Response | < 500ms | > 1s |

#### Security Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Failed Auth Attempts | 0 | > 3 in 1 hour |
| Secret Access Frequency | Normal pattern | 2x deviation |
| Unexpected API Calls | 0 | > 0 |
| Token Expiration Warnings | 0 | > 0 |

### Logging Standards

```python
import logging
import json
from datetime import datetime

class StructuredLogger:
    """Structured JSON logger for observability."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)

    def log_api_call(
        self,
        platform: str,
        operation: str,
        success: bool,
        duration_ms: float,
        correlation_id: str = None,
        error: str = None
    ):
        """
        Log API call with structured data.

        Example:
            >>> logger.log_api_call(
            ...     platform="railway",
            ...     operation="trigger_deployment",
            ...     success=True,
            ...     duration_ms=234.5,
            ...     correlation_id="req-abc123"
            ... )
        """

        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": self.service_name,
            "correlation_id": correlation_id,
            "event_type": "api_call",
            "platform": platform,
            "operation": operation,
            "success": success,
            "duration_ms": duration_ms,
            "error": error
        }

        # Remove None values
        log_entry = {k: v for k, v in log_entry.items() if v is not None}

        if success:
            self.logger.info(json.dumps(log_entry))
        else:
            self.logger.error(json.dumps(log_entry))

    def log_deployment(
        self,
        deployment_id: str,
        service: str,
        environment: str,
        status: str,
        correlation_id: str = None
    ):
        """Log deployment event."""

        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": self.service_name,
            "correlation_id": correlation_id,
            "event_type": "deployment",
            "deployment_id": deployment_id,
            "service": service,
            "environment": environment,
            "status": status
        }

        self.logger.info(json.dumps(log_entry))

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        description: str,
        correlation_id: str = None
    ):
        """Log security-related events."""

        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": self.service_name,
            "correlation_id": correlation_id,
            "event_type": "security",
            "security_event_type": event_type,
            "severity": severity,
            "description": description
        }

        if severity in ["high", "critical"]:
            self.logger.error(json.dumps(log_entry))
        else:
            self.logger.warning(json.dumps(log_entry))
```

---

## Error Handling & Recovery

### Error Categories

```python
from enum import Enum

class ErrorCategory(Enum):
    """Error categories for handling strategy."""

    TRANSIENT = "transient"          # Temporary, retry
    PERMANENT = "permanent"          # Cannot retry, fail
    AUTH = "authentication"          # Token/auth issues
    RATE_LIMIT = "rate_limit"        # Rate limited
    VALIDATION = "validation"        # Input validation failed
    EXTERNAL = "external_service"    # Third-party API down

class ErrorHandler:
    """Centralized error handling with recovery strategies."""

    async def handle_error(
        self,
        error: Exception,
        category: ErrorCategory,
        context: dict
    ):
        """
        Handle error with appropriate recovery strategy.

        Args:
            error: Exception that occurred
            category: ErrorCategory for handling strategy
            context: Context dict (operation, platform, etc.)
        """

        if category == ErrorCategory.TRANSIENT:
            # Retry with exponential backoff
            return await self._retry_with_backoff(context)

        elif category == ErrorCategory.AUTH:
            # Clear cached tokens, re-authenticate
            await self._refresh_authentication(context["platform"])
            return await self._retry_operation(context)

        elif category == ErrorCategory.RATE_LIMIT:
            # Wait for rate limit reset
            wait_time = self._get_rate_limit_reset(context["platform"])
            await asyncio.sleep(wait_time)
            return await self._retry_operation(context)

        elif category == ErrorCategory.PERMANENT:
            # Cannot recover, log and alert
            logger.error(f"Permanent error: {error}", extra=context)
            await self._send_alert(error, context)
            raise

        else:
            # Unknown category, fail safe
            logger.error(f"Unknown error category: {category}", extra=context)
            raise
```

### Rollback Strategies

```python
class RollbackManager:
    """Manage deployment rollbacks."""

    async def rollback_deployment(
        self,
        deployment_id: str,
        reason: str,
        correlation_id: str = None
    ):
        """
        Rollback failed deployment.

        Steps:
            1. Get previous successful deployment
            2. Trigger redeploy of previous version
            3. Wait for deployment to complete
            4. Verify health check
            5. Send notification
        """

        logger.warning(
            f"Initiating rollback for deployment {deployment_id}: {reason}",
            extra={"correlation_id": correlation_id}
        )

        try:
            # Get previous successful deployment
            previous = await self.railway_client.get_previous_deployment(
                deployment_id
            )

            # Trigger rollback
            new_deployment_id = await self.railway_client.rollback_deployment(
                previous["id"]
            )

            # Wait for completion
            result = await self.railway_client.wait_for_deployment(
                new_deployment_id,
                timeout=600
            )

            if result.status == "SUCCESS":
                logger.info(f"Rollback successful: {new_deployment_id}")

                # Send notification
                await self.n8n_client.execute_workflow(
                    "rollback-notification",
                    {
                        "deployment_id": deployment_id,
                        "rollback_id": new_deployment_id,
                        "reason": reason
                    }
                )

                return new_deployment_id

            else:
                raise Exception(f"Rollback failed: {result.status}")

        except Exception as e:
            logger.error(f"Rollback failed: {e}", extra={"correlation_id": correlation_id})
            # Escalate to human
            await self._escalate_to_human(deployment_id, reason, str(e))
            raise
```

---

## Deployment Architecture

### Railway Production Setup

```
┌─────────────────────────────────────────────────────┐
│             Railway Project: delightful-cat         │
│                                                     │
│  ┌────────────────────────────────────────────┐   │
│  │  Service: web (FastAPI)                     │   │
│  │  ├─ Health check: /health                   │   │
│  │  ├─ Metrics: /metrics                       │   │
│  │  ├─ Webhooks: /github-webhook, /n8n-webhook│   │
│  │  └─ Port: 8000                              │   │
│  └────────────────────────────────────────────┘   │
│                                                     │
│  ┌────────────────────────────────────────────┐   │
│  │  Service: PostgreSQL                        │   │
│  │  ├─ Database: claude_agent                  │   │
│  │  ├─ Connection pooling: enabled             │   │
│  │  └─ Backups: daily                          │   │
│  └────────────────────────────────────────────┘   │
│                                                     │
│  Environment: production                            │
│  URL: https://web-production-47ff.up.railway.app   │
└─────────────────────────────────────────────────────┘
```

### High-Availability Considerations

1. **Database Connection Pooling**
   ```python
   from sqlalchemy import create_engine
   from sqlalchemy.pool import QueuePool

   engine = create_engine(
       database_url,
       poolclass=QueuePool,
       pool_size=5,
       max_overflow=10,
       pool_pre_ping=True,  # Test connections before use
       pool_recycle=3600    # Recycle connections every hour
   )
   ```

2. **Health Checks**
   ```python
   @app.get("/health")
   async def health_check():
       """Comprehensive health check."""

       checks = {
           "database": await check_database(),
           "gcp_secrets": await check_gcp_access(),
           "railway_api": await check_railway_api(),
           "github_api": await check_github_api(),
           "n8n_api": await check_n8n_api()
       }

       all_healthy = all(checks.values())

       return {
           "status": "healthy" if all_healthy else "degraded",
           "checks": checks,
           "timestamp": datetime.utcnow().isoformat()
       }
   ```

3. **Graceful Shutdown**
   ```python
   import signal

   async def shutdown_handler(signum, frame):
       """Handle graceful shutdown."""

       logger.info("Shutdown signal received, cleaning up...")

       # Clear cached tokens
       await auth_manager.clear_all_tokens()

       # Close database connections
       await database.disconnect()

       # Wait for in-flight requests to complete
       await asyncio.sleep(5)

       logger.info("Shutdown complete")
       sys.exit(0)

   signal.signal(signal.SIGTERM, shutdown_handler)
   signal.signal(signal.SIGINT, shutdown_handler)
   ```

---

## Security Best Practices

### Checklist for Production Deployment

#### Authentication & Authorization
- [ ] WIF configured for GCP Secret Manager access
- [ ] GitHub App created with minimum permissions
- [ ] Railway API token stored in Secret Manager
- [ ] n8n API key rotated and stored securely
- [ ] No hardcoded credentials in code
- [ ] No credentials in environment variables (use Secret Manager)

#### Network Security
- [ ] All API calls use HTTPS (TLS 1.3)
- [ ] Railway app accessible via public URL with SSL
- [ ] Webhook endpoints validate sender (HMAC/signatures)
- [ ] Rate limiting enabled on webhook endpoints

#### Secrets Management
- [ ] All secrets in GCP Secret Manager
- [ ] Secret rotation schedule documented
- [ ] Secrets never logged (even partially)
- [ ] Secrets cleared from memory after use
- [ ] Audit logging enabled for secret access

#### Code Security
- [ ] Dependencies scanned for vulnerabilities (pip-audit)
- [ ] Input validation on all webhook payloads
- [ ] Type hints and validation (Pydantic)
- [ ] Error messages don't leak sensitive info
- [ ] Security headers set (CORS, CSP, etc.)

#### Monitoring & Logging
- [ ] Structured JSON logging implemented
- [ ] Correlation IDs for request tracing
- [ ] Security events logged separately
- [ ] Logs retained for 30 days
- [ ] Alerts configured for critical errors

#### Incident Response
- [ ] Rollback procedures documented
- [ ] Emergency contact list (Telegram)
- [ ] Token revocation procedures documented
- [ ] Backup and recovery tested

#### Compliance & Audit
- [ ] GCP Audit Logs enabled
- [ ] GitHub Actions logs archived
- [ ] Railway deployment history retained
- [ ] Quarterly security review scheduled

---

## Sources

- [AI Agent Security Platform - Token Security](https://www.token.security/)
- [Agentic AI Identity & Access Management - CSA](https://cloudsecurityalliance.org/artifacts/agentic-ai-identity-and-access-management-a-new-approach)
- [AI Agents and Identity Risks: 2026 Predictions - CyberArk](https://www.cyberark.com/resources/blog/ai-agents-and-identity-risks-how-security-will-shift-in-2026)
- [NIST AI Center: Agentic AI Security Best Practices](https://fedscoop.com/nist-input-agentic-ai-security-best-practices-caisi/)
- [Agentic AI Security Guide for 2026 - Strata](https://www.strata.io/blog/agentic-identity/8-strategies-for-ai-agent-security-in-2025/)
- [API Security Trends 2026 - Curity](https://curity.io/blog/api-security-trends-2026/)
- [GCP Secret Manager Best Practices](https://docs.cloud.google.com/secret-manager/docs/best-practices)
- [GCP Secret Rotation](https://docs.cloud.google.com/secret-manager/docs/secret-rotation)

---

## Next Steps

1. ✅ Implement token caching with expiration
2. ✅ Add structured logging to all API clients
3. ✅ Create comprehensive health check endpoint
4. ✅ Set up token rotation procedures
5. ✅ Configure monitoring dashboards
6. ✅ Test rollback procedures
7. ✅ Document incident response playbooks
8. ✅ Conduct quarterly security reviews

**Last Updated:** 2026-01-12
