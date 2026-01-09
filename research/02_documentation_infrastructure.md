Deep Research: Documentation Infrastructure for Growing Python/FastAPI Projects
1. Executive Summary: The Zero Tolerance Paradigm
In the realm of modern software engineering, documentation is frequently treated as a secondary artifact—an afterthought to the implementation of logic and functionality. However, for a "Personal AI System" built on high-performance frameworks like FastAPI, intended to scale and evolve over time, this reactive approach creates an unsustainable debt. The objective of establishing a "Zero Tolerance" policy for documentation errors transforms documentation from a static description into a dynamic, compiled component of the codebase. It demands that every aspect of the documentation—from the syntactic correctness of Markdown to the executability of code snippets and the fidelity of the OpenAPI contract—be validated with the same rigor as the application source code.
This report establishes the architectural and operational blueprint for such an infrastructure. The core philosophy driving this analysis is "Docs-as-Code." This paradigm dictates that documentation must live alongside source code, utilize the same version control mechanisms, and pass through the same Continuous Integration (CI) gates. A failure in documentation is a build failure. The analysis reveals that while the Python ecosystem has historically relied on Sphinx for its deep referential capabilities, the specific needs of a FastAPI project—modern aesthetic, asynchronous code examples, and tight OpenAPI integration—strongly favor a stack built around MkDocs with the Material theme, Rust-based validation tools for performance, and strict OpenAPI contract testing.
To achieve a scalable, zero-tolerance environment, this report details a multi-layered QA pipeline comprising:
 * Structural Validation: Enforcing strict Markdown syntax to prevent rendering issues.
 * Referential Integrity: Ensuring zero dead links (internal or external) using high-speed asynchronous checkers.
 * Semantic Verification: Testing code examples as executable units within the test suite, rather than static text.
 * Contractual Fidelity: Detecting breaking changes in the API schema before they reach production.
The following sections provide an exhaustive examination of the tooling landscape, architectural patterns, and workflow integrations necessary to realize this vision.
2. Foundations of Documentation Infrastructure
The selection of a documentation generator is not merely a cosmetic choice; it dictates the workflow, the extensibility of the validation pipeline, and the ease with which developers can contribute. In the Python ecosystem, this decision primarily oscillates between the traditional robustness of Sphinx and the modern agility of MkDocs.
2.1 The Static Site Generator (SSG) Landscape
The primary function of the SSG in this context is to ingest Markdown (or reStructuredText), Python docstrings, and configuration files to produce a deployable HTML artifact.
2.1.1 Sphinx: The Traditional Standard
Sphinx has been the bedrock of Python documentation for over a decade. Its strength lies in its handling of reStructuredText (reST), a markup language significantly more semantically rich than standard Markdown. Sphinx excels at complex cross-referencing, indexing, and generating non-HTML formats like LaTeX and PDF. It powers the official Python documentation and massive libraries like NumPy.
However, for a modern FastAPI project, Sphinx presents significant friction:
 * Complexity Barrier: reST syntax is verbose and strict, often discouraging casual contributions or quick edits from developers accustomed to Markdown.
 * Ecosystem Mismatch: While Sphinx supports Markdown via MyST-Parser, it is not its native tongue. FastAPI and its surrounding ecosystem (Pydantic, Starlette, Uvicorn) have largely standardized on Markdown-centric workflows.
 * Visual Limitations: Default Sphinx themes often feel dated. While modern themes exist (e.g., furo, sphinx-book-theme), achieving a "modern API" look requires significant customization compared to alternatives.
2.1.2 MkDocs and Material for MkDocs
MkDocs is a fast, simple static site generator that builds project documentation using documentation source files written in Markdown and configured with a single YAML configuration file. It has gained massive traction in the Python community, primarily due to the "Material for MkDocs" theme.
For a "Zero Tolerance" FastAPI project, MkDocs is the recommended engine for several reasons:
 * Native Markdown: It lowers the barrier to entry. Developers write standard Markdown, which renders predictably on GitHub/GitLab before even being built.
 * Performance: MkDocs is built for speed. Its development server supports instant hot-reloading, updating the browser as files are saved, which is critical for maintaining developer velocity during documentation sprints.
 * FastAPI Alignment: The creator of FastAPI, Sebastián Ramírez, heavily utilizes and advocates for MkDocs with the Material theme. Consequently, the tools for documenting FastAPI (like mkdocstrings) are optimized for this stack.
 * Plugin Ecosystem: The ecosystem offers plugins that directly support the "Zero Tolerance" goal, such as strict validation of internal links and checking for unused images or files.
2.1.3 Docusaurus: The React Contender
Docusaurus is a popular SSG from Meta (Facebook), built on React. It is widely used in the JavaScript ecosystem. While it produces beautiful sites and supports MDX (Markdown + JSX), it introduces a node.js dependency chain into a Python environment. For a Python-centric team, maintaining a package.json alongside pyproject.toml specifically for documentation adds unnecessary operational complexity. Unless the team has a strong React frontend component they wish to leverage in docs, Docusaurus creates friction in the CI pipeline (requiring both Python and Node environments) that MkDocs avoids.
2.2 Table 1: Comparative Analysis of Documentation Generators
| Feature | Sphinx | MkDocs (Material) | Docusaurus |
|---|---|---|---|
| Primary Language | Python (reST) | Python (Markdown) | Node.js (MDX) |
| Learning Curve | Steep (reST syntax) | Low (Markdown) | Moderate (React/JS) |
| Build Speed | Moderate to Slow | Fast | Moderate |
| FastAPI Integration | Good (sphinx-autodoc) | Excellent (mkdocstrings) | Manual (OpenAPI React components) |
| Visual Aesthetic | Academic/Technical | Modern/Material Design | Modern/Web App |
| CI/CD Complexity | Low (Python only) | Low (Python only) | High (Requires Node.js + Python) |
| Hot Reloading | Slower, partial | Instant, robust | Good |
Conclusion: MkDocs with Material for MkDocs is the optimal choice. It aligns with the implementation language (Python), integrates seamlessly with the framework (FastAPI), and offers the best balance of aesthetics and maintainability.
3. Validated Information Architecture and Folder Structure
Scalability in documentation requires a separation of concerns mirroring the application architecture. A flat folder of Markdown files will quickly become unmanageable as the Personal AI System grows. The structure must support distinct content types: API references, architectural decisions, user guides, and tutorials.
3.1 The src Layout Pattern
Adopting the src layout is crucial for robust packaging and testing. By placing the application code inside a src/ directory, you ensure that tests run against the installed package rather than the local folder, preventing "works on my machine" import errors. This layout also cleanly separates the application code from configuration, documentation, and test infrastructure at the root level.
3.2 Recommended Folder Structure
The following structure is designed to scale from a single service to a modular monolith or microservices architecture.
project-root/
├──.github/
│   └── workflows/
│       ├── docs-validate.yml    # CI for Linting/Links/Tests (The Gatekeeper)
│       └── docs-deploy.yml      # CD for publishing (The Publisher)
├── src/
│   └── app/
│       ├── init.py
│       ├── main.py              # Entry point
│       ├── api/                 # API Routes
│       │   ├── v1/
│       │   └── dependencies.py  # Auth dependencies for Docs
│       ├── core/                # Config, Security settings
│       └── models/              # Pydantic & ORM Models
├── docs/                        # Documentation Root
│   ├── adr/                     # Architecture Decision Records
│   │   ├── 0001-record-architecture-decisions.md
│   │   └── index.md
│   ├── api/                     # API Reference Stubs
│   │   └── index.md             # Auto-generated via mkdocstrings
│   ├── guides/                  # Narrative documentation
│   │   ├── getting-started.md
│   │   └── deployment.md
│   ├── examples/                # Executable Python scripts for docs
│   │   └── basic_usage.py
│   ├── assets/                  # Images, diagrams
│   └── index.md                 # Landing page
├── tests/
│   ├── unit/
│   └── examples/                # Tests for the documentation examples
├── mkdocs.yml                   # MkDocs Configuration
├──.markdownlint-cli2.yaml      # Strict Linter Config
├──.lychee.toml                 # Link Checker Config
├── pyproject.toml               # Python Dependencies
└── README.md                    # Repository Overview
3.3 Scaling with "Docs-as-Code"
To keep documentation in sync with code, the docs/ folder effectively becomes a monorepo for knowledge.
 * ADR (Architecture Decision Records): Located in docs/adr/. These serve as an immutable log of "why" decisions were made. As the project scales, this prevents the "lost tribal knowledge" problem.
 * Examples Directory: The docs/examples/ folder is critical. Instead of writing code blocks inside Markdown files (which are hard to test), code examples should be written here as valid Python files. They are then effectively "transcluded" into the documentation using the pymdownx.snippets extension. This allows the CI system to run these files as tests, ensuring the documentation never shows broken code.
4. Quality Assurance Layer 1: Structural Integrity (Linting)
The first line of defense in a Zero Tolerance pipeline is the linter. Markdown is permissive, which often leads to sloppy formatting that renders inconsistently across different parsers (e.g., GitHub vs. MkDocs vs. VS Code).
4.1 Linter Selection: Individual vs. Super-Linter
The prompt asks to compare Super-Linter, MegaLinter, and individual linters.
 * Super-Linter / MegaLinter: These are massive Docker images containing linters for dozens of languages (Python, Markdown, JSON, YAML, Go, etc.).
   * Pros: "One ring to rule them all." Drop it in, and it lints everything.
   * Cons: They are heavy and slow to download/initialize in CI (often gigabytes). They often lack granular configuration flexibility for specific documentation needs. For a Python/FastAPI project, 90% of the tools in MegaLinter are unnecessary bloat.
 * Individual Linters (Recommended): Selecting best-in-class tools for specific tasks (Markdown, Python) allows for faster CI runs and precise configuration.
Recommendation: Use markdownlint-cli2.
It is a Node.js-based tool but runs standalone. It is significantly faster than the Ruby implementation and supports glob patterns and distinct configuration files effectively. It is favored over the standard markdownlint-cli for its improved performance and flexible configuration handling in modern CI pipelines.
4.2 Configuration Strategy
A "Zero Tolerance" config must be strict but pragmatic. It should enforce structural consistency (headers, lists) while allowing necessary overrides for MkDocs-specific features (like HTML used for badges or complex diagrams).
Configuration File (.markdownlint-cli2.yaml):
#.markdownlint-cli2.yaml
# Zero Tolerance Configuration for Documentation

config:
  default: true
  
  # MD013: Line length.
  # Rational: Disabled because modern editors handle soft-wrapping, and 
  # hard-wrapping breaks diffs and searchability in some tools.
  MD013: false
  
  # MD033: Inline HTML.
  # Rational: Disabled because MkDocs Material often requires raw HTML 
  # for advanced formatting (e.g., <br>, <details>, or centering images).
  MD033: false
  
  # MD025: Multiple top-level headings.
  # Rational: Disabled to allow flexibility in "landing pages" or 
  # complex layouts, though generally discouraged in standard prose.
  MD025: false
  
  # MD010: Hard tabs.
  # Rational: Enforce spaces for consistency.
  MD010: true

  # MD041: First line in file should be a top level header.
  # Rational: Required for SEO and navigation clarity.
  MD041: true

# Globs to include
globs:
  - "docs/**/*.md"
  - "README.md"

# Globs to ignore
ignores:
  - "node_modules"
  - "CHANGELOG.md"
  - "docs/adr/template.md" # Often contains placeholders that trigger lint errors

This configuration ensures that all lists, headers, and spacing follow a unified standard, preventing the "sloppy" feel of unmaintained documentation.
5. Quality Assurance Layer 2: Referential Integrity (Link Checking)
Nothing erodes trust in documentation faster than a 404 error. Link checking must validate both internal references (relative links between pages) and external references (URLs to libraries, standards, etc.).
5.1 Tooling Comparison: Lychee vs. Markdown-Link-Check vs. Linkinator
 * markdown-link-check (JavaScript): A standard tool for many years. It is reliable but slow because it checks links sequentially or with limited concurrency. It runs on Node.js.
 * linkinator (JavaScript): A more modern JS alternative, often used for crawling full sites. Good for finding orphan pages but can be overkill for simple markdown checking.
 * lychee (Rust): The modern gold standard. Written in Rust, it is exponentially faster than JS-based alternatives due to async I/O handling. It can check Markdown, HTML, and reST files. It supports advanced caching, retries, and GitHub Action integration out of the box.
Recommendation: Lychee.
Its speed is critical for a "Zero Tolerance" pipeline. If link checking takes 10 minutes, developers will remove it from the required checks. Lychee runs in seconds.
5.2 Strategy for External Links
External links are flaky. A server might be temporarily down, or rate-limit the CI bot (GitHub often rate-limits requests). A naive "fail on any error" policy for external links will cause flaky builds.
Configuration (.lychee.toml):
#.lychee.toml
verbose = true
progress = true
format = "markdown"

# Internal links must always be valid
# External links are checked with retries
timeout = 20
max_retries = 3

# Exclude private/local links that can't be reached from CI
exclude = [
    "http://127.0.0.1",
    "http://localhost",
    "https://example.com"
]

# Treat all errors as fatal (Zero Tolerance)
# But rely on the exclude list to manage known unreachables
fail_on_error = true

In the GitHub Action, lychee should run on every Pull Request. If a developer adds a link to a non-existent page, the build must fail.
6. Quality Assurance Layer 3: Semantic Integrity (Code Testing)
For a developer-focused project, the documentation is the code examples. If a user copy-pastes an example and it throws an ImportError or SyntaxError, the documentation has failed.
6.1 The Challenge of Async Testing
FastAPI is inherently asynchronous. Standard Python documentation testing tools like doctest were designed for synchronous code. They struggle with async def and await keywords, often requiring complex wrappers or causing the test runner to crash.
6.2 Tooling Comparison: mktestdocs vs. pytest-codeblocks vs. Snippets
 * pytest-codeblocks: Extracts code blocks from Markdown and runs them. It supports async but requires specific annotations in the markdown to wrap code in asyncio.run(). This clutters the markdown with testing directives.
 * mktestdocs: A simpler approach that grabs code blocks and treats them as strings to valid via exec. It integrates with pytest but shares the same async limitations and context isolation issues (variables don't persist easily between blocks).
 * The "Snippets" Strategy (Recommended): Instead of writing code in Markdown, write code in Python files (src/examples/). Use the pymdownx.snippets extension to include them in the docs.
Why Snippets are Superior for Zero Tolerance:
 * Full Testability: The code lives in a .py file. It can be imported by the main test suite. Standard pytest-asyncio markers work natively.
 * IDE Support: You get full linting, autocomplete, and type checking (MyPy) in the .py file. You get none of this inside a Markdown code block.
 * Single Source of Truth: The code executed by the test runner is physically the same file presented to the reader. There is no possibility of divergence.
6.3 Implementation Details
Step 1: Write the Example
Create docs/examples/async_usage.py:
import asyncio
from app.main import create_app

async def main():
    app = create_app()
    print("App created successfully")

if __name__ == "__main__":
    asyncio.run(main())

Step 2: Test the Example
Create tests/examples/test_examples.py:
import subprocess
import sys
from pathlib import Path

def test_async_usage_example():
    example_path = Path("docs/examples/async_usage.py")
    result = subprocess.run([sys.executable, str(example_path)], capture_output=True)
    assert result.returncode == 0
    assert b"App created successfully" in result.stdout

Step 3: Embed in Documentation
In docs/guides/getting-started.md:
Here is how you start the app:python
--8<-- "docs/examples/async_usage.py"

This guarantees that if the app logic changes and breaks the example, the subprocess test will fail, blocking the PR.
7. Quality Assurance Layer 4: Contractual Fidelity (OpenAPI)
FastAPI generates an OpenAPI schema (openapi.json). As the project grows, ensuring this schema doesn't accidentally change (breaking clients) is vital.
7.1 OpenAPI Schema Customization
To produce high-quality API docs, the default schema often needs enrichment.
 * Metadata: Use app = FastAPI(title="My AI", version="1.0.0", summary="...").
 * Pydantic Integration: Pydantic models are the heart of FastAPI. Use Config to provide examples.
   class Item(BaseModel):
    name: str = Field(..., description="The name of the item")
    price: float

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Foo",
                "price": 35.4
            }
        }

   This ensures the interactive docs have realistic data pre-filled.
7.2 Breaking Change Detection
The CI pipeline must detect if a commit introduces a breaking change to the API contract.
Tool Recommendation: oasdiff
oasdiff is a Go-based tool that compares two OpenAPI specs. It is much more sophisticated than a simple text diff; it understands the semantic meaning of OpenAPI (e.g., reordering fields isn't a break, but removing a required field is).
Workflow:
The GitHub Action should:
 * Generate the openapi.json for the current branch.
 * Download the openapi.json from the main branch (stored as a build artifact).
 * Run oasdiff breaking base.json current.json.
 * If breaking changes are found, fail the build unless a specific label (e.g., breaking-change-accepted) is present on the PR.
8. Continuous Integration: The GitHub Actions Workflow
This workflow integrates all the recommendations into a single cohesive pipeline.
name: Zero Tolerance Documentation Pipeline

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  quality-gate:
    name: Documentation Quality Gate
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      # Setup Python environment
      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install Dependencies
        run: |
          pip install -r requirements.txt
          pip install mkdocs-material mkdocstrings[python] pytest httpx

      # Layer 1: Linting
      # Fails if Markdown is sloppy
      - name: Markdown Lint
        uses: DavidAnson/markdownlint-cli2-action@v16
        with:
          globs: 'docs/**/*.md'

      # Layer 2: Link Checking
      # Fails if any link (internal/external) is broken
      - name: Link Checker (Lychee)
        uses: lycheeverse/lychee-action@v1.9.0
        with:
          args: --config.lychee.toml './docs/**/*.md' --fail-on-error

      # Layer 3: Code Example Testing
      # Runs the actual python files embedded in docs
      - name: Test Documentation Snippets
        run: pytest tests/examples/

      # Layer 4: OpenAPI Contract Check
      # Only runs on PRs to check against main
      - name: Generate Current OpenAPI Spec
        if: github.event_name == 'pull_request'
        run: python src/scripts/generate_openapi.py > current_openapi.json

      - name: Download Base OpenAPI Spec
        if: github.event_name == 'pull_request'
        # Fetches the artifact from the last successful run on main
        uses: dawidd6/action-download-artifact@v3
        with:
            workflow: docs-deploy.yml
            name: openapi-spec
            path:./base_spec
            if_no_artifact_found: warn

      - name: Check for Breaking Changes
        if: github.event_name == 'pull_request' && steps.download-base.outcome == 'success'
        uses: oasdiff/oasdiff-action/breaking@main
        with:
            base: 'base_spec/openapi.json'
            revision: 'current_openapi.json'
            fail-on-diff: true

      # Layer 5: Build Integrity
      # Strict build fails on internal MkDocs warnings
      - name: Dry Run Build (Strict)
        run: mkdocs build --strict

9. Architecture Decision Records (ADRs)
For a growing project, the "why" is as important as the "how." ADRs are the industry standard for capturing this context.
9.1 Methodology and Tools
The recommended workflow utilizes log4brains. Unlike simple CLI tools like adr-tools, log4brains provides a local UI to preview ADRs and integrates seamlessly with static site generators. It treats ADRs as data, allowing you to track the status (Draft, Proposed, Accepted, Deprecated) and relationships (Supersedes, Amends) between decisions.
9.2 Writing ADRs
An ADR should be written for any architectural choice that is significant or difficult to reverse (e.g., "Using PostgreSQL over MongoDB," "Adopting MkDocs over Sphinx").
Template (Nygard Format):
 * Title: Short noun phrase.
 * Status: Proposed, Accepted, Rejected, Deprecated.
 * Context: What is the problem? What are the constraints?
 * Decision: What are we doing?
 * Consequences: What becomes easier? What becomes harder? (The "trade-offs").
9.3 Integration
Store ADRs in docs/adr/. Configure mkdocs.yml to include this directory in the navigation tree. This ensures that architectural history is searchable alongside the API reference and user guides.
10. FastAPI-Specific Considerations
10.1 Production Security: Hiding /docs
By default, FastAPI exposes /docs (Swagger UI) and /redoc publicly. For a "Personal AI System," this is convenient but potentially risky if exposed to the internet. However, disabling it entirely hinders debugging.
Recommendation: Protect /docs behind authentication rather than disabling it.
Implementation:
Use a dependency override to inject Basic Auth or check a session cookie before serving the docs endpoint.
# src/app/main.py
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
import os

app = FastAPI(docs_url=None, redoc_url=None) # Disable default routes

def get_current_username(credentials: HTTPBasicCredentials = Depends(HTTPBasic())):
    correct_user = secrets.compare_digest(credentials.username, os.getenv("DOCS_USER", "admin"))
    correct_pass = secrets.compare_digest(credentials.password, os.getenv("DOCS_PASS", "secret"))
    if not (correct_user and correct_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@app.get("/docs", include_in_schema=False)
async def get_documentation(username: str = Depends(get_current_username)):
    return get_swagger_ui_html(openapi_url="/openapi.json", title="docs")

This enables "Zero Tolerance" for security vulnerabilities related to information disclosure while maintaining utility.
10.2 Integration with External Doc Tools
The prompt asks about ReadTheDocs (RTD) vs GitBook.
 * ReadTheDocs: Historically tied to Sphinx, RTD now fully supports MkDocs. It offers excellent version hosting (e.g., keeping docs for v1.0, v1.1, and dev branch simultaneously).
   * Pros: Free for open source, handles build infrastructure, automatic versioning.
   * Cons: Less control over the build environment than GitHub Actions.
 * GitBook: A proprietary platform. It ingests Markdown but renders it using its own closed-source engine.
   * Pros: Very polished UI, excellent collaborative editing for non-developers.
   * Cons: Harder to integrate with "Zero Tolerance" CI pipelines (custom linters/tests are harder to run before the GitBook sync).
 * GitHub Pages (Recommended): Combined with mike, this offers the best control. You build the static site in your CI (where all your linters are) and push the HTML. mike handles the versioning logic (switching between v1/v2) on the client side via Javascript.
11. Tooling Comparison Summary
11.1 Static Site Generators
| Feature | MkDocs (Material) | Sphinx | Docusaurus |
|---|---|---|---|
| Philosophy | "Configuration over Code" | "Documentation as Codebase" | "Documentation as App" |
| Python Integration | Native (mkdocstrings) | Native (autodoc) | Poor (Requires Node) |
| Mobile UX | Excellent (Material) | Varies (Theme dependent) | Excellent |
| Verdict | Winner | Runner-up | Avoid (unless React team) |
11.2 Linters
| Feature | markdownlint-cli2 | Super-Linter | Standard markdownlint |
|---|---|---|---|
| Performance | High (Node.js, Parallel) | Low (Docker overhead) | Moderate (Ruby) |
| Configurability | High (Glob support) | Low (All or nothing) | Moderate |
| Verdict | Winner | Too bloated | Slower alternative |
11.3 Link Checkers
| Feature | Lychee | markdown-link-check | linkinator |
|---|---|---|---|
| Engine | Rust (Async) | Node.js | Node.js |
| Speed | Extreme | Moderate | Moderate |
| Stability | High | High | High |
| Verdict | Winner | Reliable legacy | Good for crawling |
12. Conclusion
The path to "Zero Tolerance" documentation infrastructure for a growing Python/FastAPI project is paved with rigorous automation. The days of treating documentation as a static text file are over. By adopting the MkDocs + Material ecosystem, you align with the community standards of FastAPI. By implementing Lychee and markdownlint-cli2, you ensure structural integrity at high speed. By utilizing the Snippets extension for code examples, you bridge the gap between documentation and testing, ensuring that every line of code the user sees is a line of code that has been verified. Finally, by securing the API contract with oasdiff, you protect the system's future scalability.
This architecture does not just detect errors; it prevents them from ever entering the codebase, transforming documentation from a maintenance burden into a verified, trustworthy product asset.
Implementation Checklist
 * [ ] Initialize Repo: Create src/ layout.
 * [ ] Install Tools: pip install mkdocs-material mkdocstrings[python] pytest.
 * [ ] Configure Linting: Create .markdownlint-cli2.yaml (strict but pragmatic).
 * [ ] Configure Links: Create .lychee.toml (exclude localhost, strict on internal).
 * [ ] Setup Examples: Move code blocks to src/examples/ and write pytest runners.
 * [ ] Secure Docs: Implement dependency override for /docs route.
 * [ ] Deploy CI: Commit docs-validate.yml to GitHub Actions.
 * [ ] Versioning: Set up mike for the first release deployment.
