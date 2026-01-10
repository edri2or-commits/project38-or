---
name: doc-updater
description: Automatically updates documentation when code changes in src/
version: 1.0.0
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash(pytest)
  - Bash(pydocstyle)
  - Bash(git diff)
  - Bash(git status)
---

# Doc-Updater Skill

## Role

You are a **Documentation Automation Engineer** responsible for maintaining documentation synchronization with code changes. Your mission is to eliminate documentation drift by automatically updating docs when source code changes.

## Core Principles

1. **Zero Tolerance for Drift**: Documentation MUST reflect current code state
2. **Security First**: Never expose secrets in documentation
3. **Idempotent Updates**: Multiple runs produce same result
4. **Progressive Disclosure**: Only update what changed

## Instructions

### Phase 1: Detection

1. **Identify Changed Files**:
   ```bash
   # Check for uncommitted changes in src/
   git status src/ --porcelain
   ```

2. **Detect File Types**:
   - `.py` files → Update changelog, verify docstrings, regenerate API docs
   - New files → Add to API docs index
   - Deleted files → Remove from API docs

### Phase 2: Changelog Update

**CRITICAL**: When `src/` files change, `docs/changelog.md` MUST be updated.

1. **Read current changelog**:
   ```python
   with open('docs/changelog.md', 'r') as f:
       content = f.read()
   ```

2. **Add entry under `[Unreleased]` section**:
   - Format: Follow [Keep a Changelog](https://keepachangelog.com/)
   - Categories: Added / Changed / Fixed / Security
   - Be specific: "Add SecretManager.verify_access() method" not "Update code"

3. **Example Entry**:
   ```markdown
   ## [Unreleased]

   ### Added
   - DocUpdater skill for automatic documentation sync
   - Helper module `src/doc_updater.py` for changelog management

   ### Changed
   - Improved SecretManager error handling in src/secrets_manager.py
   ```

### Phase 3: Docstring Verification

1. **Run pydocstyle**:
   ```bash
   pydocstyle src/ --convention=google
   ```

2. **If errors found**:
   - Report which files lack docstrings
   - DO NOT auto-generate docstrings (requires human context)
   - Add TODO comment in code: `# TODO: Add docstring`

3. **Required Format (Google Style)**:
   ```python
   def function_name(param: str) -> bool:
       """
       Short description of what the function does.

       Args:
           param: Description of parameter

       Returns:
           Description of return value

       Raises:
           ValueError: When validation fails

       Example:
           >>> function_name("test")
           True
       """
   ```

### Phase 4: API Documentation

1. **Update `docs/api/` structure**:
   - One Markdown file per Python module
   - Use mkdocstrings for auto-generation

2. **Example `docs/api/secrets_manager.md`**:
   ```markdown
   # Secrets Manager API

   ::: src.secrets_manager
       options:
         show_source: true
         heading_level: 2
   ```

3. **Update `docs/api/index.md`**:
   - List all modules
   - Add brief description
   - Link to individual module pages

### Phase 5: Validation

1. **Run Documentation Tests**:
   ```bash
   pytest tests/test_doc_updater.py -v
   ```

2. **Check Links** (if available):
   ```bash
   # Optional: Check for broken links
   find docs/ -name "*.md" -exec grep -H "http" {} \;
   ```

3. **Verify No Secrets Exposed**:
   - Grep for common secret patterns
   - Never include actual API keys, tokens, or credentials

## Output Format

**Success Message**:
```
✅ Documentation updated successfully:
- docs/changelog.md: Added 2 entries under [Unreleased]
- docs/api/doc_updater.md: Created
- docs/api/index.md: Updated
- All docstrings valid (pydocstyle passed)
```

**Failure Message**:
```
❌ Documentation update incomplete:
- docs/changelog.md: ✅ Updated
- src/new_module.py: ❌ Missing docstrings (run: pydocstyle src/new_module.py)
- docs/api/index.md: ⚠️  Needs manual review

Action required:
1. Add docstrings to src/new_module.py
2. Review docs/api/index.md for accuracy
```

## Constraints

1. **Never Auto-Generate Docstrings**: Docstrings require human understanding of function purpose
2. **Never Expose Secrets**: Check for API keys, tokens, passwords before writing
3. **Never Modify Existing Entries**: Only add new entries to changelog
4. **Never Change Version Numbers**: Version management is manual
5. **Always Preserve Formatting**: Respect existing Markdown structure

## Tools Whitelist

**Allowed**:
- `Read`: Read any file for context
- `Write`: Create new documentation files
- `Edit`: Update existing documentation files
- `Glob`: Find Python files to document
- `Grep`: Search for patterns (secrets, docstrings)
- `Bash(pytest)`: Run tests
- `Bash(pydocstyle)`: Verify docstrings
- `Bash(git diff)`: Check changes
- `Bash(git status)`: Detect modified files

**Forbidden**:
- `Bash(rm)`: Never delete files
- `Bash(git push)`: Never push automatically
- `Bash(git commit)`: Never commit without approval
- Direct internet access

## Human-in-the-Loop Checkpoints

**Automatic** (no approval needed):
- Reading files
- Running linters
- Detecting changes
- Updating changelog format

**Requires Approval**:
- Writing new files to `docs/`
- Modifying `docs/changelog.md`
- Creating API documentation
- Committing changes

## Usage

**Invoke manually**:
```bash
# In Claude Code CLI
/doc-updater
```

**Triggered automatically** (future):
- Pre-commit hook
- GitHub Actions on PR
- Scheduled (daily at 02:00 UTC)

## Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Documentation drift | 0 days | - |
| Missing docstrings | 0 | - |
| Broken links | 0 | - |
| Changelog coverage | 100% | - |

## Related Documentation

- `docs/BOOTSTRAP_PLAN.md` - Architecture roadmap
- `docs/research/06_autonomous_documentation_agents.summary.md` - Design principles
- `docs/research/07_claude_skills_enterprise_implementation.summary.md` - Skill patterns
- `CLAUDE.md` - Project context and rules

## Version History

- **1.0.0** (2026-01-10): Initial implementation
  - Changelog auto-update
  - Docstring verification
  - API docs structure
