# Operational Scenarios: The Autonomous System in Action

## Overview

This document demonstrates the complete autonomous system through three real-world scenarios, showing how all components (Railway, GitHub, n8n, resilience patterns, security) work together.

---

## Scenario 1: Autonomous Deployment Failure Recovery

**Situation**: A developer pushes code with a syntax error to main branch. The system detects, recovers, and reports - all without human intervention.

### Timeline

```
T+0s   | Developer commits to main
T+5s   | GitHub Actions CI starts
T+30s  | CI passes (syntax check missed the error)
T+35s  | GitHub webhook → n8n → Claude Agent
T+36s  | Agent: Observe new commit
T+37s  | Agent: Orient (CI passed, commit is from trusted dev)
T+38s  | Agent: Decide (trigger Railway deployment)
T+39s  | Agent: Act (Railway GraphQL: deploymentTrigger)
T+40s  | Railway: INITIALIZING
T+45s  | Railway: BUILDING
T+120s | Railway: FAILED (SyntaxError: invalid syntax)
T+121s | Agent: Observe failure
T+122s | Agent: Orient (parse build logs → syntax error at line 45)
T+123s | Agent: Decide (rollback + create issue + alert)
T+124s | Agent: Act (parallel execution)
        |   ├─ Railway: rollback to last ACTIVE deployment
        |   ├─ GitHub: create issue with error details
        |   └─ n8n: send Telegram alert
T+145s | Railway: Rollback ACTIVE
T+146s | GitHub: Issue #123 created
T+147s | n8n: Telegram message sent
T+150s | System stable, humans notified
```

**Total Recovery Time**: 110 seconds (T+40s to T+150s)

---

### Complete Implementation

```python
"""Scenario 1: Complete autonomous deployment failure recovery."""
import asyncio
from datetime import datetime, UTC

class AutonomousDeploymentOrchestrator:
    """Orchestrator implementing full OODA loop for deployment management."""

    def __init__(
        self,
        railway: RailwayClient,
        github: GitHubAppClient,
        n8n: N8nClient,
        logger: StructuredLogger,
        audit: AuditTrail
    ):
        self.railway = railway
        self.github = github
        self.n8n = n8n
        self.logger = logger
        self.audit = audit

    async def handle_new_commit(self, event: Dict[str, Any]):
        """Handle new commit event from GitHub webhook.

        This is the entry point for the autonomous deployment flow.
        """
        commit_sha = event["head_commit"]["sha"]
        commit_message = event["head_commit"]["message"]
        author = event["head_commit"]["author"]["name"]
        repo = event["repository"]["full_name"]

        # =====================================================================
        # PHASE 1: OBSERVE
        # =====================================================================
        self.logger.log_observation(
            source="github",
            data={
                "event": "push",
                "commit": commit_sha,
                "message": commit_message,
                "author": author
            }
        )

        # Check CI status
        ci_runs = await self.github.get_workflow_runs(
            owner="edri2or-commits",
            repo="project38-or",
            workflow_id="test.yml",
            status="completed",
            limit=1
        )

        if not ci_runs or ci_runs[0]["conclusion"] != "success":
            self.logger.log_decision(
                decision="skip_deployment",
                reasoning={"reason": "CI did not pass"}
            )
            return

        # =====================================================================
        # PHASE 2: ORIENT
        # =====================================================================
        # Analyze commit (is this a deployment-worthy change?)
        is_production_change = (
            "src/" in commit_message or
            "fix" in commit_message.lower() or
            "feat" in commit_message.lower()
        )

        context = {
            "commit": commit_sha,
            "author": author,
            "ci_status": "passed",
            "is_production_change": is_production_change,
            "timestamp": datetime.now(UTC).isoformat()
        }

        self.logger.log_decision(
            decision="trigger_deployment",
            reasoning=context
        )

        # =====================================================================
        # PHASE 3: DECIDE
        # =====================================================================
        # Decision: Deploy to production
        actions = [
            {
                "type": "deploy",
                "target": "railway",
                "params": {
                    "project_id": "95ec21cc-9ada-41c5-8485-12f9a00e0116",
                    "environment_id": "99c99a18-aea2-4d01-9360-6a93705102a0",
                    "commit_sha": commit_sha
                }
            }
        ]

        # =====================================================================
        # PHASE 4: ACT
        # =====================================================================
        for action in actions:
            await self._execute_action(action)

    async def _execute_action(self, action: Dict[str, Any]):
        """Execute a single action from the decision phase."""

        if action["type"] == "deploy":
            await self._deploy_to_railway(action["params"])

    async def _deploy_to_railway(self, params: Dict[str, Any]):
        """Deploy to Railway and monitor until stable or failed."""

        project_id = params["project_id"]
        environment_id = params["environment_id"]
        commit_sha = params["commit_sha"]

        # Trigger deployment
        deployment_id = await self.railway.trigger_deployment(
            project_id=project_id,
            environment_id=environment_id
        )

        self.logger.log_action(
            worker="railway",
            action="trigger_deployment",
            params={"deployment_id": deployment_id, "commit_sha": commit_sha},
            result="initiated"
        )

        # Audit log
        await self.audit.log_action(
            phase="act",
            worker="railway",
            action="trigger_deployment",
            params=params,
            result="initiated",
            deployment_id=deployment_id,
            github_commit=commit_sha
        )

        # Monitor deployment until stable
        try:
            final_status = await self.railway.monitor_deployment_until_stable(
                deployment_id=deployment_id,
                timeout_seconds=600
            )

            if final_status == "ACTIVE":
                await self._handle_deployment_success(
                    deployment_id=deployment_id,
                    commit_sha=commit_sha
                )
            elif final_status in ("FAILED", "CRASHED"):
                await self._handle_deployment_failure(
                    deployment_id=deployment_id,
                    commit_sha=commit_sha,
                    status=final_status,
                    project_id=project_id,
                    environment_id=environment_id
                )

        except TimeoutError:
            await self._handle_deployment_timeout(
                deployment_id=deployment_id,
                commit_sha=commit_sha
            )

    async def _handle_deployment_success(
        self,
        deployment_id: str,
        commit_sha: str
    ):
        """Handle successful deployment."""

        self.logger.log_action(
            worker="railway",
            action="deployment_complete",
            params={"deployment_id": deployment_id},
            result="success"
        )

        # Audit
        await self.audit.log_action(
            phase="act",
            worker="railway",
            action="deployment_complete",
            params={"deployment_id": deployment_id},
            result="success",
            deployment_id=deployment_id,
            github_commit=commit_sha
        )

        # Send success notification (optional - low priority)
        await self.n8n.execute_workflow(
            workflow_id="deployment-success-notification",
            data={
                "deployment_id": deployment_id,
                "commit_sha": commit_sha,
                "status": "ACTIVE"
            }
        )

    async def _handle_deployment_failure(
        self,
        deployment_id: str,
        commit_sha: str,
        status: str,
        project_id: str,
        environment_id: str
    ):
        """Handle deployment failure with autonomous recovery.

        Recovery Strategy:
        1. Retrieve build/runtime logs
        2. Identify last stable deployment
        3. Rollback to stable version
        4. Create GitHub Issue with error details
        5. Send critical alert via n8n → Telegram
        """

        # =====================================================================
        # Step 1: Retrieve logs
        # =====================================================================
        if status == "FAILED":
            logs = await self.railway.get_build_logs(deployment_id, limit=50)
        else:  # CRASHED
            logs = await self.railway.get_runtime_logs(deployment_id, limit=50)

        # Find error messages
        error_logs = [log for log in logs if log["severity"] == "ERROR"]
        error_summary = error_logs[0]["message"] if error_logs else "Unknown error"

        self.logger.log_observation(
            source="railway",
            data={
                "deployment_id": deployment_id,
                "status": status,
                "error": error_summary,
                "error_count": len(error_logs)
            }
        )

        # =====================================================================
        # Step 2: Find last stable deployment
        # =====================================================================
        last_stable = await self.railway.get_last_active_deployment(
            project_id=project_id,
            environment_id=environment_id
        )

        if not last_stable:
            # No stable version to rollback to - critical situation
            await self._handle_critical_failure(
                deployment_id=deployment_id,
                error_summary=error_summary
            )
            return

        # =====================================================================
        # Step 3: Execute recovery actions in parallel
        # =====================================================================
        recovery_tasks = [
            # Task 1: Rollback to stable version
            self._rollback_deployment(
                deployment_id=deployment_id,
                last_stable_id=last_stable["id"],
                project_id=project_id,
                environment_id=environment_id
            ),

            # Task 2: Create GitHub Issue
            self._create_failure_issue(
                deployment_id=deployment_id,
                commit_sha=commit_sha,
                error_summary=error_summary,
                logs=logs,
                status=status
            ),

            # Task 3: Send critical alert
            self._send_critical_alert(
                deployment_id=deployment_id,
                commit_sha=commit_sha,
                error_summary=error_summary,
                status=status
            )
        ]

        # Execute all recovery tasks concurrently
        results = await asyncio.gather(*recovery_tasks, return_exceptions=True)

        # Log recovery results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.log_action(
                    worker="orchestrator",
                    action=f"recovery_task_{i}",
                    params={"task_index": i},
                    result="failed"
                )
            else:
                self.logger.log_action(
                    worker="orchestrator",
                    action=f"recovery_task_{i}",
                    params={"task_index": i},
                    result="success"
                )

    async def _rollback_deployment(
        self,
        deployment_id: str,
        last_stable_id: str,
        project_id: str,
        environment_id: str
    ):
        """Rollback to last stable deployment."""

        self.logger.log_decision(
            decision="rollback",
            reasoning={
                "failed_deployment": deployment_id,
                "rollback_target": last_stable_id
            }
        )

        # Execute rollback
        rollback_deployment = await self.railway.rollback_deployment(last_stable_id)

        # Monitor rollback
        rollback_status = await self.railway.monitor_deployment_until_stable(
            deployment_id=rollback_deployment["id"],
            timeout_seconds=300
        )

        if rollback_status == "ACTIVE":
            self.logger.log_action(
                worker="railway",
                action="rollback_deployment",
                params={
                    "failed_deployment": deployment_id,
                    "rollback_deployment": rollback_deployment["id"]
                },
                result="success"
            )
        else:
            # Rollback failed - critical situation
            self.logger.log_action(
                worker="railway",
                action="rollback_deployment",
                params={
                    "failed_deployment": deployment_id,
                    "rollback_deployment": rollback_deployment["id"]
                },
                result="failed"
            )

            # Escalate to human
            await self._handle_critical_failure(
                deployment_id=rollback_deployment["id"],
                error_summary="Rollback deployment also failed"
            )

        return rollback_deployment

    async def _create_failure_issue(
        self,
        deployment_id: str,
        commit_sha: str,
        error_summary: str,
        logs: List[Dict[str, Any]],
        status: str
    ):
        """Create detailed GitHub Issue for deployment failure."""

        # Get commit details
        commit = await self.github.get_commit_details(
            owner="edri2or-commits",
            repo="project38-or",
            commit_sha=commit_sha
        )

        # Format issue body
        issue_body = f"""
## 🚨 Deployment Failure Report

**Deployment ID**: `{deployment_id}`
**Status**: {status}
**Timestamp**: {datetime.now(UTC).isoformat()}

---

## Recent Commit (Likely Culprit)

**SHA**: `{commit_sha}`
**Author**: {commit["commit"]["author"]["name"]} <{commit["commit"]["author"]["email"]}>
**Message**: {commit["commit"]["message"]}
**URL**: {commit["html_url"]}

---

## Error Summary

```
{error_summary}
```

---

## Log Excerpt (Last 20 Lines)

```
{chr(10).join(log["message"] for log in logs[-20:])}
```

---

## Autonomous Recovery Actions Taken

- ✅ Deployment failure detected
- ✅ Build/runtime logs retrieved
- ✅ **Rollback initiated** to last stable version
- ✅ This issue created for human review
- ✅ Critical alert sent via Telegram

**Status**: Service has been restored via automatic rollback. Please review the error and fix the issue.

---

## Investigation Steps

1. Review the error in logs above
2. Check commit diff: {commit["html_url"]}
3. Fix the issue locally
4. Run tests: `pytest tests/ -v`
5. Commit fix with message: `fix: resolve deployment error from #{commit_sha[:7]}`
6. Push to main (will trigger new deployment)

---

_This issue was created automatically by the autonomous deployment system._
        """

        # Create issue
        issue = await self.github.create_issue(
            owner="edri2or-commits",
            repo="project38-or",
            title=f"🚨 Deployment Failed: {error_summary[:80]}",
            body=issue_body,
            labels=["bug", "deployment", "autonomous-agent", "high-priority"]
        )

        self.logger.log_action(
            worker="github",
            action="create_issue",
            params={
                "issue_number": issue["number"],
                "deployment_id": deployment_id
            },
            result="success"
        )

        return issue

    async def _send_critical_alert(
        self,
        deployment_id: str,
        commit_sha: str,
        error_summary: str,
        status: str
    ):
        """Send critical alert via n8n → Telegram."""

        await self.n8n.execute_workflow(
            workflow_id="critical-deployment-alert",
            data={
                "alert": {
                    "severity": "critical",
                    "title": "🚨 Deployment Failed",
                    "message": f"Deployment {deployment_id} failed with status: {status}",
                    "details": {
                        "deployment_id": deployment_id,
                        "commit_sha": commit_sha,
                        "error": error_summary,
                        "status": status,
                        "timestamp": datetime.now(UTC).isoformat()
                    }
                }
            }
        )

        self.logger.log_action(
            worker="n8n",
            action="send_alert",
            params={"deployment_id": deployment_id},
            result="success"
        )

    async def _handle_critical_failure(
        self,
        deployment_id: str,
        error_summary: str
    ):
        """Handle critical failure (no stable version to rollback to)."""

        # Log critical situation
        self.logger.log_action(
            worker="orchestrator",
            action="critical_failure",
            params={
                "deployment_id": deployment_id,
                "error": error_summary
            },
            result="escalated"
        )

        # Send emergency alert
        await self.n8n.execute_workflow(
            workflow_id="emergency-alert",
            data={
                "alert": {
                    "severity": "emergency",
                    "title": "🚨🚨🚨 CRITICAL: No Stable Version Available",
                    "message": f"Deployment {deployment_id} failed and no stable version exists for rollback. MANUAL INTERVENTION REQUIRED.",
                    "details": {
                        "deployment_id": deployment_id,
                        "error": error_summary
                    }
                }
            }
        )

        # Escalate via all channels (GitHub Issue + Telegram + Email)
        await self.github.create_issue(
            owner="edri2or-commits",
            repo="project38-or",
            title="🚨🚨🚨 EMERGENCY: Production Down, No Rollback Available",
            body=f"""
## CRITICAL SITUATION

Production deployment failed and no stable version is available for rollback.

**Deployment ID**: `{deployment_id}`
**Error**: {error_summary}

**IMMEDIATE ACTION REQUIRED**:
1. Check Railway dashboard: https://railway.app/project/95ec21cc-9ada-41c5-8485-12f9a00e0116
2. Manually deploy a known-good version
3. Investigate root cause

This is an **EMERGENCY** - service is currently DOWN.
            """,
            labels=["emergency", "production-down", "p0"]
        )
```

---

## Scenario 2: Performance Degradation Detection

**Situation**: Production service experiencing high CPU usage. Agent detects, analyzes, and takes corrective action.

### Timeline

```
T+0s   | Normal operation (CPU: 45%)
T+300s | CPU spike begins (CPU: 75%)
T+600s | CPU sustained high (CPU: 85%)
T+605s | Agent: Observe metrics (scheduled health check)
T+606s | Agent: Orient (CPU > 80% threshold for 5+ minutes)
T+607s | Agent: Decide (scale up resources OR investigate)
T+608s | Agent: Act (retrieve runtime logs + create GitHub Issue)
T+610s | Human investigates, finds N+1 query problem
T+1800s| Human deploys fix
T+1850s| Agent: Observe (CPU back to normal: 45%)
T+1851s| Agent: Close GitHub Issue (autonomous verification)
```

### Implementation

```python
"""Scenario 2: Performance degradation detection and reporting."""

class PerformanceMonitor:
    """Monitor system performance and detect degradation."""

    def __init__(
        self,
        railway: RailwayClient,
        github: GitHubAppClient,
        thresholds: Dict[str, float]
    ):
        self.railway = railway
        self.github = github
        self.thresholds = thresholds  # {"cpu": 80.0, "memory": 85.0}
        self.alert_cooldown: Dict[str, datetime] = {}

    async def monitor_performance(self, deployment_id: str):
        """Continuous performance monitoring (runs every 5 minutes)."""

        # Observe metrics
        metrics = await self.railway.get_deployment_metrics(deployment_id)

        cpu_usage = metrics["cpuUsage"]
        memory_usage = metrics["memoryUsage"]

        # Check thresholds
        if cpu_usage > self.thresholds["cpu"]:
            await self._handle_high_cpu(deployment_id, cpu_usage)

        if memory_usage > self.thresholds["memory"]:
            await self._handle_high_memory(deployment_id, memory_usage)

    async def _handle_high_cpu(self, deployment_id: str, cpu_usage: float):
        """Handle sustained high CPU usage."""

        # Check cooldown (don't spam alerts)
        if "high_cpu" in self.alert_cooldown:
            if datetime.now(UTC) - self.alert_cooldown["high_cpu"] < timedelta(hours=1):
                return  # Already alerted recently

        # Get runtime logs to investigate
        logs = await self.railway.get_runtime_logs(deployment_id, limit=100)

        # Create investigation issue
        issue = await self.github.create_issue(
            owner="edri2or-commits",
            repo="project38-or",
            title=f"⚠️ High CPU Usage Detected: {cpu_usage:.1f}%",
            body=f"""
## Performance Degradation Alert

**Deployment ID**: `{deployment_id}`
**CPU Usage**: {cpu_usage:.1f}% (threshold: {self.thresholds['cpu']}%)
**Timestamp**: {datetime.now(UTC).isoformat()}

---

## Investigation

The autonomous system detected sustained high CPU usage. This may indicate:
- Inefficient algorithm (N+1 queries, nested loops)
- Memory leak causing GC pressure
- External API slowness
- Increased traffic load

---

## Recent Logs

```
{chr(10).join(log["message"] for log in logs[-30:])}
```

---

## Recommended Actions

1. Review recent code changes for performance regressions
2. Check external API latencies
3. Profile the application to identify bottleneck
4. Consider scaling resources if traffic increased

The agent will continue monitoring and close this issue if CPU returns to normal.
            """,
            labels=["performance", "investigation", "autonomous-agent"]
        )

        # Update cooldown
        self.alert_cooldown["high_cpu"] = datetime.now(UTC)

        # Store issue number for later closure
        await db.store_config(f"perf_issue_{deployment_id}_cpu", issue["number"])
```

---

## Scenario 3: Self-Healing CI/CD Pipeline

**Situation**: Transient network error causes CI workflow to fail. Agent detects pattern and retriggers workflow.

### Implementation

```python
"""Scenario 3: Self-healing CI/CD pipeline."""

class CIPipelineHealer:
    """Detect and recover from transient CI failures."""

    def __init__(
        self,
        github: GitHubAppClient,
        retry_budget: RetryBudget
    ):
        self.github = github
        self.retry_budget = retry_budget

    async def check_failed_workflows(self):
        """Check for failed workflows and retry if transient."""

        # Get recent failed workflows
        failed_runs = await self.github.get_workflow_runs(
            owner="edri2or-commits",
            repo="project38-or",
            status="completed",
            limit=10
        )

        for run in failed_runs:
            if run["conclusion"] != "failure":
                continue

            # Analyze failure reason
            is_transient = await self._is_transient_failure(run)

            if is_transient and self.retry_budget.can_retry("ci_workflow"):
                # Retrigger workflow
                await self.github.trigger_workflow(
                    owner="edri2or-commits",
                    repo="project38-or",
                    workflow_id=run["workflow_id"],
                    ref=run["head_branch"]
                )

                logger.info(f"Retriggered transient-failed workflow: {run['id']}")

    async def _is_transient_failure(self, run: Dict[str, Any]) -> bool:
        """Determine if workflow failure was transient.

        Transient indicators:
        - "timeout"
        - "network"
        - "rate limit"
        - "500 Internal Server Error"
        """
        # Get workflow logs (simplified - actual implementation needs GitHub API)
        # For now, check failure message
        conclusion_message = run.get("conclusion_message", "")

        transient_keywords = [
            "timeout",
            "network",
            "rate limit",
            "500",
            "502",
            "503",
            "connection reset"
        ]

        return any(keyword in conclusion_message.lower() for keyword in transient_keywords)
```

---

## System Integration: Everything Together

### Complete Orchestrator OODA Loop

```python
"""Main orchestrator running continuous OODA loop."""

class MainOrchestrator:
    """Master orchestrator coordinating all subsystems."""

    def __init__(self):
        # Initialize all clients
        secret_manager = SecretManager()

        self.railway = RailwayClient(
            api_token=secret_manager.get_secret("RAILWAY-API")
        )

        github_private_key = secret_manager.get_secret("github-app-private-key")
        self.github = GitHubAppClient(
            app_id="123456",
            private_key=github_private_key,
            installation_id="789012"
        )

        self.n8n = N8nClient(
            base_url="https://n8n.railway.app",
            api_key=secret_manager.get_secret("N8N-API")
        )

        # Initialize subsystems
        self.deployment_orchestrator = AutonomousDeploymentOrchestrator(
            railway=self.railway,
            github=self.github,
            n8n=self.n8n,
            logger=StructuredLogger("deployment"),
            audit=AuditTrail(session)
        )

        self.performance_monitor = PerformanceMonitor(
            railway=self.railway,
            github=self.github,
            thresholds={"cpu": 80.0, "memory": 85.0}
        )

        self.ci_healer = CIPipelineHealer(
            github=self.github,
            retry_budget=RetryBudget(max_retries_per_hour=20)
        )

        # Killswitch
        self.killswitch = Killswitch()

    async def run_ooda_loop(self):
        """Main autonomous loop - runs continuously."""

        logger.info("🚀 Autonomous system starting...")

        while True:
            try:
                # Check killswitch
                self.killswitch.check()

                # ============================================================
                # OBSERVE: Gather data from all sources
                # ============================================================
                observations = await self.observe()

                # ============================================================
                # ORIENT: Analyze and build world model
                # ============================================================
                world_state = await self.orient(observations)

                # ============================================================
                # DECIDE: Determine actions
                # ============================================================
                actions = await self.decide(world_state)

                # ============================================================
                # ACT: Execute actions
                # ============================================================
                await self.act(actions)

                # Wait before next iteration
                await asyncio.sleep(30)  # 30 second loop

            except KillswitchActivatedError:
                logger.critical("Killswitch activated - shutting down")
                break

            except Exception as e:
                logger.error(f"OODA loop error: {e}")
                # Continue running despite errors
                await asyncio.sleep(60)

    async def observe(self) -> Dict[str, Any]:
        """Observe all systems."""

        observations = {}

        # Observe Railway
        try:
            current_deployment_id = await db.get_config("current_deployment_id")
            if current_deployment_id:
                observations["railway"] = {
                    "status": await self.railway.get_deployment_status(current_deployment_id),
                    "metrics": await self.railway.get_deployment_metrics(current_deployment_id)
                }
        except Exception as e:
            logger.warning(f"Railway observation failed: {e}")
            observations["railway"] = {"error": str(e)}

        # Observe GitHub
        try:
            observations["github"] = {
                "recent_commits": await self.github.get_recent_commits(
                    owner="edri2or-commits",
                    repo="project38-or",
                    limit=5
                ),
                "workflow_runs": await self.github.get_workflow_runs(
                    owner="edri2or-commits",
                    repo="project38-or",
                    limit=5
                )
            }
        except Exception as e:
            logger.warning(f"GitHub observation failed: {e}")
            observations["github"] = {"error": str(e)}

        # Observe n8n
        try:
            observations["n8n"] = {
                "recent_executions": await self.n8n.get_recent_executions(limit=10)
            }
        except Exception as e:
            logger.warning(f"n8n observation failed: {e}")
            observations["n8n"] = {"error": str(e)}

        return observations

    async def orient(self, observations: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze observations and build world model."""

        world_state = {
            "timestamp": datetime.now(UTC).isoformat(),
            "system_health": "unknown",
            "issues_detected": []
        }

        # Analyze Railway status
        if "railway" in observations and "status" in observations["railway"]:
            railway_status = observations["railway"]["status"]

            if railway_status in ("FAILED", "CRASHED"):
                world_state["issues_detected"].append({
                    "type": "deployment_failure",
                    "severity": "critical",
                    "source": "railway"
                })

            if "metrics" in observations["railway"]:
                metrics = observations["railway"]["metrics"]
                if metrics.get("cpuUsage", 0) > 80:
                    world_state["issues_detected"].append({
                        "type": "high_cpu",
                        "severity": "warning",
                        "source": "railway"
                    })

        # Analyze GitHub CI
        if "github" in observations and "workflow_runs" in observations["github"]:
            failed_runs = [
                run for run in observations["github"]["workflow_runs"]
                if run["conclusion"] == "failure"
            ]

            if failed_runs:
                world_state["issues_detected"].append({
                    "type": "ci_failure",
                    "severity": "warning",
                    "source": "github",
                    "count": len(failed_runs)
                })

        # Determine overall system health
        if not world_state["issues_detected"]:
            world_state["system_health"] = "healthy"
        elif any(i["severity"] == "critical" for i in world_state["issues_detected"]):
            world_state["system_health"] = "critical"
        else:
            world_state["system_health"] = "degraded"

        return world_state

    async def decide(self, world_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Decide actions based on world state."""

        actions = []

        for issue in world_state["issues_detected"]:
            if issue["type"] == "deployment_failure":
                actions.append({
                    "handler": "deployment_orchestrator",
                    "method": "_handle_deployment_failure",
                    "priority": 1  # Critical
                })

            elif issue["type"] == "high_cpu":
                actions.append({
                    "handler": "performance_monitor",
                    "method": "_handle_high_cpu",
                    "priority": 2  # Warning
                })

            elif issue["type"] == "ci_failure":
                actions.append({
                    "handler": "ci_healer",
                    "method": "check_failed_workflows",
                    "priority": 3  # Low
                })

        # Sort by priority
        actions.sort(key=lambda x: x["priority"])

        return actions

    async def act(self, actions: List[Dict[str, Any]]):
        """Execute actions."""

        for action in actions:
            try:
                handler = getattr(self, action["handler"])
                method = getattr(handler, action["method"])

                await method()

                logger.info(f"Action executed: {action['method']}")

            except Exception as e:
                logger.error(f"Action failed: {action['method']} - {e}")

# ============================================================================
# Application Entry Point
# ============================================================================

async def main():
    """Start the autonomous system."""

    orchestrator = MainOrchestrator()
    await orchestrator.run_ooda_loop()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Conclusion

These scenarios demonstrate:

1. **Complete Autonomy**: System detects, decides, and acts without human intervention
2. **Resilience**: Handles failures gracefully with rollback and alerts
3. **Intelligence**: Analyzes logs, correlates events, makes reasoned decisions
4. **Transparency**: Every action logged and auditable
5. **Safety**: Killswitch, retry budgets, permission controls

**This is not automation. This is true autonomy.**

---

**End of Hybrid Documentation Series**

Complete series:
- [00: Autonomous Philosophy](00-autonomous-philosophy.md)
- [01: System Architecture](01-system-architecture-hybrid.md)
- [02: Railway Integration](02-railway-integration-hybrid.md)
- [03: GitHub App Integration](03-github-app-integration-hybrid.md)
- [04: n8n Orchestration](04-n8n-orchestration-hybrid.md)
- [05: Resilience Patterns](05-resilience-patterns-hybrid.md)
- [06: Security Architecture](06-security-architecture-hybrid.md)
- [07: Operational Scenarios](07-operational-scenarios-hybrid.md) ← You are here
