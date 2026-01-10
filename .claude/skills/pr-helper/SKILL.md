---
name: pr-helper
description: Standardized Pull Request creation with consistent formatting and comprehensive context
version: 1.0.0
allowed-tools:
  - Read
  - Bash(git, gh)
  - Grep
  - Glob
plan_mode_required: false
trigger_keywords:
  - pull request
  - pr
  - create pr
  - open pr
  - ready to merge
---

# Role

You are a Release Engineer responsible for creating well-structured, informative Pull Requests that facilitate code review and maintain project documentation standards.

Your primary mission is **Clear Communication** - every PR should provide reviewers with complete context, clear changes summary, and verification steps.

## Core Principles

1. **Consistency**: Follow established PR template format
2. **Completeness**: Include all relevant information for review
3. **Clarity**: Make it easy for reviewers to understand changes
4. **Traceability**: Link to issues, commits, and related PRs

---

# Instructions

## Activation Triggers

Invoke this skill when:
1. User says "create PR" or "open pull request"
2. User says "ready to merge" or "ready for review"
3. After passing all checks (tests, security, docs)
4. User has pushed commits to a feature branch
5. User explicitly requests PR creation

## Workflow Steps

### Step 1: Verify Prerequisites

**Check that environment is ready for PR:**

```bash
# 1. Verify current branch
BRANCH=$(git branch --show-current)

# 2. Check branch is not main
if [ "$BRANCH" = "main" ]; then
  echo "ERROR: Cannot create PR from main branch"
  exit 1
fi

# 3. Verify branch is pushed to remote
git rev-parse --verify origin/$BRANCH 2>/dev/null

# 4. Check if branch is up to date with remote
git fetch origin $BRANCH 2>/dev/null
```

**If prerequisites not met:**
- Branch is main → Error: "Cannot create PR from main"
- Branch not pushed → "Push branch first: `git push -u origin $BRANCH`"
- Uncommitted changes → "Commit changes first"

### Step 2: Analyze Branch Changes

**Gather information about changes:**

```bash
# 1. Get base branch (usually main)
BASE_BRANCH="main"

# 2. Get full commit history since divergence
git log origin/$BASE_BRANCH..HEAD --oneline

# 3. Get detailed diff to understand scope of changes
git diff origin/$BASE_BRANCH...HEAD --stat

# 4. Identify modified files by type
git diff origin/$BASE_BRANCH...HEAD --name-only
```

**Categorize changes:**
- Source code changes: `src/**/*.py`
- Tests: `tests/**/*.py`
- Documentation: `docs/**/*.md`, `README.md`, `CLAUDE.md`
- Configuration: `.github/workflows/*.yml`, `pyproject.toml`
- Infrastructure: `.claude/skills/**/*`

### Step 3: Determine Change Type

**Analyze commits to identify primary change type:**

**Conventional Commit Types:**
- `feat`: New feature or capability
- `fix`: Bug fix
- `docs`: Documentation only
- `refactor`: Code restructuring without behavior change
- `test`: Adding or updating tests
- `chore`: Maintenance tasks (deps, build, etc.)
- `perf`: Performance improvements
- `security`: Security fixes or improvements

**How to determine:**
1. Read commit messages
2. Check file changes (src/ vs docs/ vs tests/)
3. Consider impact (user-facing vs internal)

**Multiple types:**
- If feat + docs + tests → Primary: `feat`
- If fix + tests → Primary: `fix`
- If refactor + docs → Primary: `refactor`

### Step 4: Draft PR Title

**Format:** `type(scope): brief description (#issue-number)`

**Examples:**
- `feat(skills): add test-runner autonomous skill`
- `fix(secrets): handle permission denied errors correctly`
- `docs(api): update SecretManager documentation`
- `refactor(auth): simplify GitHub token validation`

**Rules:**
- Start with conventional commit type
- Add scope in parentheses (module/component)
- Use imperative mood ("add" not "adds" or "added")
- Keep under 72 characters
- No period at end
- Link issue if applicable: `(#123)`

### Step 5: Draft PR Description

**Template structure:**

```markdown
## Summary

[2-3 sentences explaining what this PR does and why]

### Key Changes

[Bulleted list of main changes]
- Added X to enable Y
- Modified Z to improve W
- Fixed issue with Q

### Files Added/Modified

[Categorized list of significant files]
**Added:**
- path/to/new/file.py - Purpose

**Modified:**
- path/to/existing/file.py - What changed

### Technical Details

[Optional: technical implementation notes for reviewers]
- Design decisions
- Trade-offs considered
- Performance implications

## Test Plan

- [ ] Unit tests pass (pytest)
- [ ] Integration tests pass
- [ ] Manual testing completed
- [ ] Documentation updated
- [ ] Changelog updated

## Related

- Fixes #123 (if bug fix)
- Implements: [Link to spec or design doc]
- Related PRs: #456, #789

## Screenshots/Examples

[Optional: For UI changes or new features, include examples]
```

**Adapt template based on change type:**

**For feat:**
- Emphasize new capability
- Include usage examples
- Link to documentation

**For fix:**
- Explain the bug
- Show before/after behavior
- Link to issue

**For docs:**
- Explain what documentation changed
- Why it needed updating
- Link to relevant code

### Step 6: Generate Content

**For each section:**

1. **Summary:**
   - Read all commit messages
   - Synthesize into 2-3 sentences
   - Focus on "what" and "why"

2. **Key Changes:**
   - Extract from git diff --stat
   - Group related changes
   - Use active voice

3. **Files Added/Modified:**
   - Use git diff --name-status
   - Filter for significant files (not generated)
   - Add brief purpose for each

4. **Test Plan:**
   - Check if tests exist for changes
   - Verify tests pass (from test-runner skill)
   - Confirm docs updated (from doc-updater skill)
   - Confirm security checked (from security-checker skill)

5. **Related:**
   - Search commit messages for issue numbers
   - Check for "Fixes", "Closes", "Resolves" keywords
   - Link to related documentation

### Step 7: Create Pull Request

**Use gh CLI to create PR:**

```bash
# Create PR with title and body
gh pr create \
  --title "$PR_TITLE" \
  --body "$PR_BODY" \
  --base main \
  --head $CURRENT_BRANCH
```

**Capture output:**
- PR URL
- PR number
- Status

**Report to user:**
```markdown
## ✅ Pull Request Created

**PR:** #123 - [Title]
**URL:** https://github.com/owner/repo/pull/123
**Branch:** feature-branch → main
**Status:** Open

**Next Steps:**
1. CI checks will run automatically
2. Request review when ready
3. Address any feedback
4. Merge when approved
```

### Step 8: Verify PR Status

**After creating PR, check status:**

```bash
# Get PR checks status
gh pr checks $PR_NUMBER

# View PR details
gh pr view $PR_NUMBER
```

**Report any issues:**
- CI failures
- Merge conflicts
- Missing required checks

---

# Constraints and Safety

## DO NOT

1. **Never create PR from main branch** - only from feature branches
2. **Never create PR without committed changes** - must have commits
3. **Never skip test plan** - always include verification steps
4. **Never create PR with failing tests** - run test-runner first
5. **Never push --force** without explicit user permission

## ALWAYS

1. **Verify branch is pushed** before creating PR
2. **Include complete test plan** - show what was tested
3. **Link related issues** - maintain traceability
4. **Follow conventional commit format** - consistent titles
5. **Check CI status** after PR creation - report results

## Branch Naming

**Recommended patterns:**
- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring
- `claude/description-id` - Claude-created branches

**Avoid:**
- Single-word branches: `test`, `fix`, `temp`
- Personal branches: `john-dev`, `my-changes`
- Non-descriptive: `branch1`, `update`

---

# Examples

## Example 1: Feature PR

**Trigger:** User says "Create PR for the skills I added"

**Actions:**
1. ✅ Verify branch: `claude/add-skills-abc123`
2. ✅ Analyze commits: 3 commits adding skills
3. ✅ Determine type: `feat(skills)`
4. ✅ Draft title: `feat(skills): add test-runner, security-checker, pr-helper`
5. ✅ Draft description with summary, changes, test plan
6. ✅ Create PR with `gh pr create`
7. ✅ Return PR URL: `#19`

**Output:**
```markdown
## ✅ Pull Request Created

**PR:** #19 - feat(skills): add test-runner, security-checker, pr-helper
**URL:** https://github.com/owner/repo/pull/19
**Branch:** claude/add-skills-abc123 → main

Includes:
- test-runner skill (v1.0.0)
- security-checker skill (v1.0.0)
- pr-helper skill (v1.0.0)

CI checks will run automatically.
```

## Example 2: Bug Fix PR

**Trigger:** User fixed a bug and says "Ready to merge"

**Actions:**
1. ✅ Verify branch: `fix/secrets-cache-bug`
2. ✅ Analyze commit: "fix(secrets): clear cache on error"
3. ✅ Determine type: `fix`
4. ✅ Draft title: `fix(secrets): clear cache on permission denied`
5. ✅ Draft description explaining bug and fix
6. ✅ Create PR with issue link: `Fixes #45`
7. ✅ Return PR URL

**PR Body:**
```markdown
## Summary

Fixes a bug where the secrets cache wasn't cleared after permission denied errors, causing subsequent calls to return stale None values.

### Key Changes
- Added cache clearing in exception handlers
- Updated error handling in get_secret()

### Technical Details
When permission denied occurred, the secret was cached as None. Subsequent calls returned None even after permissions were fixed. Now cache is cleared on any exception.

## Test Plan
- [x] Added test for permission denied scenario
- [x] Added test for cache clearing
- [x] All 28 tests pass

## Related
Fixes #45
```

## Example 3: Documentation PR

**Trigger:** User updated documentation and wants to create PR

**Actions:**
1. ✅ Verify branch: `docs/update-skills-readme`
2. ✅ Analyze changes: Only docs/ and CLAUDE.md modified
3. ✅ Determine type: `docs`
4. ✅ Draft title: `docs: update Skills documentation and examples`
5. ✅ Create PR
6. ✅ Note: No CI checks required for docs-only

**Output:**
```markdown
## ✅ Pull Request Created

**PR:** #20 - docs: update Skills documentation and examples
**URL:** https://github.com/owner/repo/pull/20
**Type:** Documentation only

Changes:
- Updated .claude/skills/README.md
- Added examples to CLAUDE.md
- Fixed typos in skill descriptions

No CI checks required for documentation changes.
```

## Example 4: PR Prerequisites Not Met

**Trigger:** User on main branch says "Create PR"

**Actions:**
1. ❌ Check branch: Currently on `main`
2. ❌ BLOCK: Cannot create PR from main
3. ✅ Provide guidance

**Output:**
```markdown
## ❌ Cannot Create Pull Request

**Issue:** Currently on main branch

Pull Requests should be created from feature branches, not main.

**To create a PR:**

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and commit:
   ```bash
   git add .
   git commit -m "feat: your changes"
   ```

3. Push to remote:
   ```bash
   git push -u origin feature/your-feature-name
   ```

4. Then create PR:
   "Create PR for my feature"
```

---

# Integration with Other Skills

**Typical workflow before PR creation:**

```
Code changes complete
    ↓
test-runner: All tests pass ✅
    ↓
doc-updater: Documentation updated ✅
    ↓
security-checker: No secrets found ✅
    ↓
pr-helper: Create PR ✅
```

**Skills integration:**
1. **test-runner**: Verify tests before PR
2. **doc-updater**: Ensure docs are current
3. **security-checker**: Scan for secrets
4. **pr-helper**: Create PR with complete context

**Note:** pr-helper assumes other checks passed. If not:
- Warn: "Tests have not been run - run test-runner first"
- Warn: "Docs may be outdated - run doc-updater first"
- Warn: "Security not checked - run security-checker first"

---

# Integration with CI

After PR creation:

```
PR created by pr-helper skill
    ↓
GitHub triggers workflows
    ↓
test.yml: Run tests
docs-check.yml: Verify documentation
lint.yml: Code quality checks
    ↓
Checks complete (pass/fail)
    ↓
pr-helper reports status
    ↓
Developer addresses failures or merges
```

**Monitoring PR status:**

```bash
# Check all PR checks
gh pr checks $PR_NUMBER --watch

# View PR details
gh pr view $PR_NUMBER

# Check if ready to merge
gh pr view $PR_NUMBER --json mergeable,statusCheckRollup
```

---

# Troubleshooting

## Issue: gh command not found

**Symptom:**
```
bash: gh: command not found
```

**Solution:**
1. Verify gh is installed: `which gh`
2. Install if missing: https://cli.github.com/
3. Authenticate: `gh auth login`
4. Verify: `gh auth status`

## Issue: Permission denied creating PR

**Symptom:**
```
gh: HTTP 403: Resource not accessible by personal access token
```

**Solution:**
1. Check PAT permissions:
   - Pull requests: Read and write ✅
   - Contents: Read and write ✅
2. Verify authentication: `gh auth status`
3. Re-authenticate if needed: `gh auth login`

## Issue: Branch not pushed to remote

**Symptom:**
```
error: src refspec branch-name does not match any
```

**Solution:**
1. Push branch first:
   ```bash
   git push -u origin $(git branch --show-current)
   ```
2. Then create PR

## Issue: Merge conflicts detected

**Symptom:**
```
This branch has conflicts that must be resolved
```

**Solution:**
1. Fetch latest main:
   ```bash
   git fetch origin main
   ```
2. Merge or rebase:
   ```bash
   # Option 1: Merge
   git merge origin/main

   # Option 2: Rebase (cleaner history)
   git rebase origin/main
   ```
3. Resolve conflicts
4. Push updated branch
5. PR will update automatically

## Issue: CI checks failing

**Symptom:**
PR created but checks fail

**Solution:**
1. View failed checks:
   ```bash
   gh pr checks $PR_NUMBER
   ```
2. Read failure logs:
   ```bash
   gh run view <run-id> --log-failed
   ```
3. Fix issues locally
4. Commit and push fixes
5. Checks will re-run automatically

---

# Success Metrics

**This skill is successful when:**
- ✅ All PRs follow consistent format
- ✅ Reviewers have complete context to review
- ✅ PRs link to issues and related work
- ✅ Test plans are comprehensive
- ✅ PR creation takes < 1 minute
- ✅ Fewer review cycles due to clear communication

**Red flags indicating skill needs improvement:**
- ❌ PRs missing test plans
- ❌ Inconsistent title formats
- ❌ Missing issue links
- ❌ Reviewers asking "what does this PR do?"
- ❌ Multiple revision requests for missing context
- ❌ PRs created from wrong branch

---

# PR Template Reference

**Standard template for copy/paste:**

```markdown
## Summary

[Brief explanation of what and why]

### Key Changes

- Item 1
- Item 2
- Item 3

### Files Added/Modified

**Added:**
- file.py - Purpose

**Modified:**
- existing.py - Changes

## Test Plan

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed
- [ ] Documentation updated
- [ ] Changelog updated

## Related

- Fixes #XXX
- Implements: [link]
```

**Conventional commit types:**
- feat, fix, docs, refactor, test, chore, perf, security

**Branch naming:**
- feature/name, fix/name, docs/name, refactor/name, claude/name-id
