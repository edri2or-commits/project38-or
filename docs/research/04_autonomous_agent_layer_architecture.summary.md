# Summary: Autonomous Agent Layer Architecture

**Source**: `research/04_autonomous_agent_layer_architecture.md`

---

## Summary

Blueprint for implementing autonomous agents (Security Scanner, Self-Healing) within a single-developer FastAPI/Railway environment. Core philosophy: **"Database-as-Backbone"** - use PostgreSQL for queuing, locking, vectors, and messaging instead of adding Redis/RabbitMQ.

**Key Agents:**
- **Security Scanner**: Continuous SAST/SCA/DAST scanning
- **Self-Healing Agent**: Reflexion pattern for automatic error remediation
- **Learning System**: Vector-based memory for agent improvement

---

## Actionable Practices

1. **PostgreSQL as Infrastructure:**
   - Job Queue: `SKIP LOCKED` pattern
   - Scheduler Locks: `pg_try_advisory_lock()`
   - Vector Memory: `pgvector` extension
   - Messaging: `LISTEN/NOTIFY`

2. **Security Triad:**
   - SAST: Bandit (`bandit -r src/ -f json`)
   - SCA: Trivy (`trivy filesystem / --format json`)
   - DAST: OWASP ZAP (API-based active scanning)

3. **Reflexion Loop (Self-Healing):**
   ```
   Signal → Actor (LLM generates fix) → Execute →
   Reflector (analyze failure) → Retry with feedback
   ```

4. **Progressive Autonomy:**
   - Level 1: Observer (read-only, notify)
   - Level 2: Proposer (create PRs, human approval)
   - Level 3: Actor (auto-fix with confidence > 0.95)

5. **Railway Rollback:**
   - Use Railway GraphQL API for `deploymentRollback`
   - Worker process monitors deployment health

---

## Risks / Assumptions

| Risk | Impact | Mitigation |
|------|--------|------------|
| Agent goal hijacking | Malicious actions | Context segregation, input tagging |
| Infinite loops | Resource drain | Advisory locks, timeouts |
| Memory poisoning | Bad learned behavior | Constitutional Judge, human verification |
| Tool misuse | Destructive commands | Scoped DB roles, tool whitelists |

**Assumptions:**
- Railway deployment
- PostgreSQL with pgvector
- Single-developer maintenance capacity
- n8n for external notifications

---

## Architecture Decisions Impact

| Decision | Implication |
|----------|-------------|
| No Redis/RabbitMQ | Simpler ops, PostgreSQL does everything |
| Dual-process (Web/Worker) | Heavy tasks don't block API |
| Reflexion pattern | Self-correcting agents with memory |
| Progressive autonomy | Graduated trust, human gates |

**Implementation Phases:**
1. Foundation (Advisory locks, pgvector)
2. Sentinel (Security scanning)
3. Healer (Error remediation)
4. Brain (Learning system)
