# Summary: Documentation Infrastructure - Zero Tolerance

**Source**: `research/01_documentation_infrastructure_zero_tolerance.md`

---

## Summary

This document establishes a "Docs-as-Code" paradigm for Python/FastAPI projects, treating documentation as a compiled component that must pass CI gates with the same rigor as application code.

**Key Recommendations:**
- **Generator**: MkDocs with Material theme (over Sphinx/Docusaurus) - aligns with FastAPI ecosystem
- **Linting**: markdownlint-cli2 for strict Markdown validation
- **Link Checking**: Lychee (Rust-based) for high-speed link validation
- **Code Examples**: Use `pymdownx.snippets` to include real Python files instead of inline code blocks
- **API Contract**: Use `oasdiff` for OpenAPI breaking change detection
- **ADRs**: Use log4brains for Architecture Decision Records

---

## Actionable Practices

1. **Set up 4-layer QA pipeline:**
   - Structural (linting) → Referential (links) → Semantic (code tests) → Contractual (OpenAPI)

2. **Adopt the Snippets pattern:**
   - Write examples in `docs/examples/*.py`
   - Test them via pytest
   - Include in docs via `--8<-- "docs/examples/file.py"`

3. **Protect FastAPI /docs endpoint:**
   - Add HTTP Basic Auth instead of disabling
   - Use environment variables for credentials

4. **Use GitHub Pages + mike for versioning**

---

## Risks / Assumptions

| Risk | Impact | Mitigation |
|------|--------|------------|
| Node.js dependency (markdownlint) | Build complexity | Isolate in CI step |
| External links flakiness | False CI failures | Use Lychee with retries + exclude list |
| Code examples drift | Broken docs | Snippets pattern with pytest |

**Assumptions:**
- Team uses GitHub Actions
- Documentation lives alongside code
- FastAPI as primary framework

---

## Architecture Decisions Impact

| Decision | Before | After |
|----------|--------|-------|
| Doc generator | Ad-hoc | MkDocs + Material |
| Code examples | Inline (untested) | External files (tested) |
| Link validation | Manual | Automated via Lychee |
| API changes | Breaking silently | oasdiff blocks breaking |

**Key Change**: Documentation failures should block PRs just like test failures.
