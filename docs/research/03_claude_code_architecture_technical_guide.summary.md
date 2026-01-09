# Summary: Claude Code Architecture - Technical Guide

**Source**: `research/03_claude_code_architecture_technical_guide.md`

---

## Summary

Comprehensive technical guide for Claude Code as an autonomous agent platform. Covers the tool system, Hooks for control, MCP protocol for extensibility, and enterprise governance mechanisms.

**Key Components:**
- **Tools**: LS, Glob, Grep, Read, Edit, Write, Bash - the agent's "hands"
- **Hooks**: User-defined scripts at lifecycle events (PreToolUse, PostToolUse)
- **MCP**: Model Context Protocol for external tool integration
- **CLAUDE.md**: Project-specific context/instructions

---

## Actionable Practices

1. **Hook-Based Control:**
   ```json
   {
     "hook_event_name": "PreToolUse",
     "tool_name": "Edit",
     "tool_input": { "file_path": "..." }
   }
   ```
   - Exit code 2 = Block the action
   - JSON output provides feedback to agent

2. **MCP Server Configuration:**
   - Stdio: Local subprocess communication
   - HTTP: Remote services
   - Hierarchy: Managed > Project > User

3. **CLAUDE.md for Context:**
   - Root level: Global standards
   - Subdirectory: Component-specific rules
   - Use `@path/to/file` for imports

4. **Security Layers:**
   - `managed-settings.json` for org policies
   - `disableBypassPermissionsMode: "disable"`
   - Sandbox/container isolation recommended

---

## Risks / Assumptions

| Risk | Impact | Mitigation |
|------|--------|------------|
| Bash tool misuse | System damage | PreToolUse hooks, sandboxing |
| Schema-less Bash | Hard to validate | Pattern matching in hooks |
| MCP server trust | Code execution | Managed allowlists |
| Lazy loading context | Token waste | Use progressive disclosure |

**Assumptions:**
- Claude Code CLI environment
- Developer has terminal access
- Project has CLAUDE.md configured

---

## Architecture Decisions Impact

| Decision | Implication |
|----------|-------------|
| Use Hooks | Deterministic control over agent actions |
| MCP integration | Extend agent with custom tools |
| Managed settings | Enterprise policy enforcement |
| CLAUDE.md hierarchy | Context-aware agent behavior |

**Tool Risk Levels:**
| Tool | Risk Level |
|------|------------|
| Bash | Critical |
| Edit/Write | High |
| Read/LS/Grep | Low |
