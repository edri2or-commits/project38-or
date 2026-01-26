# ADR-016: MCP Implementation Decision Matrix

**Date**: 2026-01-26
**Status**: Accepted
**Deciders**: User (edri2or-commits), Claude AI Agent (System Audit)
**Tags**: mcp, gateway, architecture, consolidation

---

## Context

### The Problem

System audit (2026-01-26) identified **7 parallel MCP Gateway/Bridge implementations** causing confusion:

| Implementation | Location | Language | Lines | Status |
|----------------|----------|----------|-------|--------|
| MCP Gateway (Primary) | `src/mcp_gateway/` | Python | 1,683 | Production |
| MCP Gateway CloudRun | `services/mcp-gateway-cloudrun/` | Python | 412 | Production |
| MCP Router (Cloud Function) | `cloud_functions/mcp_router/` | Python | 1,100+ | Production |
| MCP Proxy | `cloud_functions/mcp_proxy/` | Python | ~200 | Production |
| GCS MCP Bridge | `services/gcs-mcp-bridge/` | Node.js | N/A | Experimental |
| GCS MCP Relay | `services/gcs-mcp-relay/` | Node.js | 5,531 | Experimental |
| S3 MCP Bridge | `services/s3-mcp-bridge/` | Node.js | N/A | Experimental |
| Railway MCP Bridge | `services/railway-mcp-bridge/` | Node.js | N/A | Experimental |

### Root Cause

Iterative development trying different approaches to bypass Anthropic proxy limitations:
1. First: Direct MCP Gateway on Railway (`src/mcp_gateway/`)
2. Then: Cloud Run for better scaling (`services/mcp-gateway-cloudrun/`)
3. Then: Cloud Functions for serverless (`cloud_functions/mcp_router/`)
4. Then: Various bridge/relay approaches for specific protocols

### Impact

- New developers don't know which implementation to use
- Maintenance effort multiplied
- Inconsistent feature sets across implementations
- Tech debt accumulation

---

## Decision

### Primary Implementations (KEEP)

| Use Case | Implementation | URL | When to Use |
|----------|----------------|-----|-------------|
| **Local Claude Code** | MCP Gateway | `https://or-infra.com/mcp` | Default for local development |
| **Cloud Sessions** | MCP Router | `https://mcp-router-*.run.app` | When behind Anthropic proxy |
| **GitHub Actions** | Cloud Function | Via WIF authentication | CI/CD automation |

### Experimental (ARCHIVE)

| Implementation | Decision | Reason |
|----------------|----------|--------|
| `services/gcs-mcp-bridge/` | **ARCHIVE** | Superseded by MCP Router |
| `services/gcs-mcp-relay/` | **ARCHIVE** | Superseded by MCP Router |
| `services/s3-mcp-bridge/` | **ARCHIVE** | Not needed (no S3 usage) |
| `services/railway-mcp-bridge/` | **ARCHIVE** | Superseded by MCP Gateway |

### Decision Matrix

```
Need MCP access?
│
├─ Running locally with Claude Code?
│   └─ USE: MCP Gateway (https://or-infra.com/mcp)
│
├─ Running in Anthropic cloud session?
│   └─ USE: MCP Router (Cloud Run) via GCP Tunnel
│
├─ Running in GitHub Actions?
│   └─ USE: Cloud Function with WIF authentication
│
└─ Building new MCP integration?
    └─ EXTEND: src/mcp_gateway/tools/ (add new tool module)
```

---

## Consequences

### Positive
- Clear guidance for developers
- Reduced maintenance surface (4 → 3 implementations)
- Consistent documentation

### Negative
- Need to migrate any code depending on archived services
- Short-term effort to archive/document

### Neutral
- Existing production services unaffected

---

## Implementation

### Phase 1: Documentation (This ADR)
- [x] Create decision matrix
- [x] Document which implementation for which use case

### Phase 2: Archive Experimental Services
- [ ] Move `services/gcs-mcp-bridge/` to `archive/`
- [ ] Move `services/gcs-mcp-relay/` to `archive/`
- [ ] Move `services/s3-mcp-bridge/` to `archive/`
- [ ] Move `services/railway-mcp-bridge/` to `archive/`

### Phase 3: Update Documentation
- [ ] Update CLAUDE.md with simplified MCP section
- [ ] Add README.md to `services/` with active services only

---

## Update Log

| Date | Update | Author |
|------|--------|--------|
| 2026-01-26 | Initial ADR created from system audit | Claude (Audit) |
