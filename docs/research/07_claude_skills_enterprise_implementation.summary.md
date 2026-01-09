# Summary: Claude Skills - Enterprise Implementation

**Source**: `research/07_claude_skills_enterprise_implementation.md`

---

## Summary

Strategic framework for deploying Claude Skills in enterprise environments. Skills are version-controlled, reusable agent behaviors that transform AI from ad-hoc prompting to standardized workflow automation.

**Key Differentiator**: Skills vs System Prompts
- Skills: Dynamic loading, persistent state, scoped tooling, Git-versioned
- System Prompts: Static, ephemeral, global scope

---

## Actionable Practices

1. **SKILL.md Structure:**
   ```yaml
   ---
   name: database-migration-helper
   description: guide for PostgreSQL migrations using TypeORM
   allowed-tools:
     - Read
     - Bash(npm run migrate:*)
   ---

   ## Role
   You are a Database Reliability Engineer...

   ## Instructions
   1. Inspect current schema
   2. Draft migration file
   3. Verify syntax
   ```

2. **Essential MCP Servers:**
   - `@modelcontextprotocol/server-filesystem`
   - `@modelcontextprotocol/server-github`
   - `@modelcontextprotocol/server-postgres`
   - `mcherukara/claude-deep-research`
   - `chromadb/mcp-server` (vector memory)

3. **Human-in-the-Loop Enforcement:**
   - Use `plan_mode_required` parameter
   - Two-phase: Plan → Verify → Execute
   - Agent cannot write until plan approved

4. **Skill Patterns:**
   - **Scaffolding**: Generate boilerplate from templates
   - **Chaining**: Skill triggers another skill
   - **Deep Research**: Wrap research MCP, output to ADR

5. **Shared Infrastructure:**
   ```
   .claude/
   └── plugins/
       └── engineering-std/
           ├── .mcp.json
           └── skills/
               ├── git-commit/SKILL.md
               └── db-migration/SKILL.md
   ```

---

## Risks / Assumptions

| Risk | Impact | Mitigation |
|------|--------|------------|
| Skill Drift | Inconsistent behavior | PR reviews for SKILL.md changes |
| Hallucinated Destruction | System damage | Sandboxing, allowed-tools whitelist |
| Context Saturation | Token waste | Progressive disclosure, <500 lines |
| Wrong Skill Activation | Incorrect actions | Descriptive keywords in frontmatter |

**Assumptions:**
- Claude Code CLI environment
- Team uses Git for skill distribution
- MCP servers available

---

## Architecture Decisions Impact

| Decision | Implication |
|----------|-------------|
| Skills over prompts | Version control, distribution, scoping |
| MCP integration | Extends agent with external tools |
| plan_mode_required | Mandatory human verification |
| Plugin architecture | Team-wide skill sharing |

**Implementation Roadmap:**
1. **MVP**: Doc-updater skill (low risk, high visibility)
2. **Beta**: Feature scaffolding (standardization)
3. **Production**: Safe-refactor with test loop

**Benchmarks:**
- Claude 3.5 Sonnet: ~49% on SWE-bench Verified
- Strength: Strategic multi-step workflows
- Comparison: Better than Aider for architecture, safer than OpenDevin
