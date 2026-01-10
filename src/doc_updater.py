"""Documentation updater module for automatic changelog and API docs management.

This module provides utilities for maintaining documentation synchronization
with code changes, specifically:
- Changelog management
- Docstring verification
- API documentation structure
"""

import re
import subprocess
from pathlib import Path


class ChangelogEntry:
    """Represents a single changelog entry.

    Attributes:
        category: The changelog category (Added, Changed, Fixed, Security)
        description: Human-readable description of the change
    """

    VALID_CATEGORIES = ["Added", "Changed", "Fixed", "Security", "Deprecated", "Removed"]

    def __init__(self, category: str, description: str):
        """Initialize a changelog entry.

        Args:
            category: Must be one of: Added, Changed, Fixed, Security, Deprecated, Removed
            description: Description of the change

        Raises:
            ValueError: If category is not valid
        """
        if category not in self.VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category '{category}'. "
                f"Must be one of: {', '.join(self.VALID_CATEGORIES)}"
            )
        self.category = category
        self.description = description

    def __str__(self) -> str:
        """Format entry as markdown list item.

        Returns:
            Formatted markdown string
        """
        return f"- {self.description}"


class ChangelogManager:
    """Manages changelog file updates following Keep a Changelog format.

    Example:
        >>> manager = ChangelogManager("docs/changelog.md")
        >>> manager.add_entry("Added", "New feature X")
        >>> manager.write()
    """

    def __init__(self, changelog_path: str = "docs/changelog.md"):
        """Initialize changelog manager.

        Args:
            changelog_path: Path to changelog file
        """
        self.changelog_path = Path(changelog_path)
        self.entries: list[ChangelogEntry] = []

    def read_current(self) -> str:
        """Read current changelog content.

        Returns:
            Current changelog content as string

        Raises:
            FileNotFoundError: If changelog file doesn't exist
        """
        if not self.changelog_path.exists():
            raise FileNotFoundError(f"Changelog not found: {self.changelog_path}")
        return self.changelog_path.read_text(encoding="utf-8")

    def add_entry(self, category: str, description: str) -> None:
        """Add a new entry to the changelog.

        Args:
            category: Changelog category (Added, Changed, Fixed, etc.)
            description: Description of the change

        Raises:
            ValueError: If category is invalid
        """
        entry = ChangelogEntry(category, description)
        self.entries.append(entry)

    def _find_unreleased_section(self, content: str) -> tuple[int, int]:
        """Find the [Unreleased] section boundaries in changelog.

        Args:
            content: Full changelog content

        Returns:
            Tuple of (start_line, end_line) indices

        Raises:
            ValueError: If [Unreleased] section not found
        """
        lines = content.split("\n")

        # Find [Unreleased] header
        unreleased_idx = None
        for i, line in enumerate(lines):
            if "[Unreleased]" in line:
                unreleased_idx = i
                break

        if unreleased_idx is None:
            raise ValueError("Could not find [Unreleased] section in changelog")

        # Find next version section (starts with ##)
        next_section_idx = len(lines)
        for i in range(unreleased_idx + 1, len(lines)):
            if lines[i].startswith("## [") and "[Unreleased]" not in lines[i]:
                next_section_idx = i
                break

        return unreleased_idx, next_section_idx

    def write(self, dry_run: bool = False) -> str:
        """Write changelog entries to file.

        Args:
            dry_run: If True, return content without writing file

        Returns:
            Updated changelog content

        Raises:
            FileNotFoundError: If changelog file doesn't exist
            ValueError: If [Unreleased] section not found
        """
        if not self.entries:
            return self.read_current()

        current_content = self.read_current()
        lines = current_content.split("\n")

        unreleased_start, unreleased_end = self._find_unreleased_section(current_content)

        # Group entries by category
        entries_by_category = {}
        for entry in self.entries:
            if entry.category not in entries_by_category:
                entries_by_category[entry.category] = []
            entries_by_category[entry.category].append(entry)

        # Build new entries section
        new_entries = []
        for category in ChangelogEntry.VALID_CATEGORIES:
            if category in entries_by_category:
                # Check if category section already exists
                category_exists = False
                for i in range(unreleased_start, unreleased_end):
                    if lines[i].strip() == f"### {category}":
                        category_exists = True
                        # Find where to insert (after category header)
                        insert_idx = i + 1
                        # Add new entries
                        for entry in entries_by_category[category]:
                            lines.insert(insert_idx, str(entry))
                            insert_idx += 1
                        break

                if not category_exists:
                    new_entries.append(f"\n### {category}")
                    for entry in entries_by_category[category]:
                        new_entries.append(str(entry))

        # If we have new categories to add
        if new_entries:
            # Find insertion point (after [Unreleased] header, skip empty lines)
            insert_idx = unreleased_start + 1
            while insert_idx < unreleased_end and lines[insert_idx].strip() == "":
                insert_idx += 1

            # Insert new category sections
            for line in reversed(new_entries):
                lines.insert(insert_idx, line)

        updated_content = "\n".join(lines)

        if not dry_run:
            self.changelog_path.write_text(updated_content, encoding="utf-8")

        return updated_content


class DocstringChecker:
    """Checks Python files for missing or malformed docstrings.

    Uses pydocstyle internally to validate Google-style docstrings.
    """

    def __init__(self, base_path: str = "src"):
        """Initialize docstring checker.

        Args:
            base_path: Base directory to check (default: src)
        """
        self.base_path = Path(base_path)

    def check(self, file_path: str | None = None) -> tuple[bool, str]:
        """Check docstrings using pydocstyle.

        Args:
            file_path: Specific file to check, or None for all files in base_path

        Returns:
            Tuple of (success: bool, output: str)
                success: True if all docstrings valid
                output: pydocstyle output or success message

        Example:
            >>> checker = DocstringChecker()
            >>> success, output = checker.check("src/secrets_manager.py")
            >>> if not success:
            ...     print(f"Errors: {output}")
        """
        target = file_path if file_path else str(self.base_path)

        try:
            result = subprocess.run(
                ["pydocstyle", target, "--convention=google"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                return True, f"✅ All docstrings valid in {target}"
            else:
                return False, result.stdout

        except FileNotFoundError:
            return False, "❌ pydocstyle not installed. Run: pip install pydocstyle"


def get_changed_python_files() -> list[str]:
    """Get list of changed Python files in src/ using git.

    Returns:
        List of file paths that have been modified

    Example:
        >>> files = get_changed_python_files()
        >>> print(f"Changed: {files}")
        ['src/secrets_manager.py', 'src/github_auth.py']
    """
    try:
        # Get unstaged changes
        result = subprocess.run(
            ["git", "status", "src/", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )

        changed_files = []
        for line in result.stdout.split("\n"):
            if line.strip():
                # Parse git status output (format: "XY filename")
                parts = line.strip().split(maxsplit=1)
                if len(parts) == 2:
                    status, filepath = parts
                    if filepath.endswith(".py"):
                        changed_files.append(filepath)

        return changed_files

    except subprocess.CalledProcessError:
        # Not a git repo or git not available
        return []


def detect_secrets_in_content(content: str) -> list[str]:
    """Detect potential secrets in documentation content.

    Args:
        content: Text content to scan

    Returns:
        List of potential secret patterns found

    Example:
        >>> content = "API_KEY=sk_test_123456"
        >>> secrets = detect_secrets_in_content(content)
        >>> if secrets:
        ...     print(f"⚠️  Potential secrets found: {secrets}")
    """
    # Common secret patterns
    patterns = [
        r"['\"]?(sk|pk)_[a-z]+_[A-Za-z0-9]{20,}['\"]?",  # API keys (stripe-like)
        r"['\"]?ghp_[A-Za-z0-9]{36}['\"]?",  # GitHub PAT
        r"['\"]?gho_[A-Za-z0-9]{36}['\"]?",  # GitHub OAuth
        r"ANTHROPIC[_-]API[_-]KEY\s*=\s*['\"]?[A-Za-z0-9\-_]{20,}",  # Anthropic
        r"OPENAI[_-]API[_-]KEY\s*=\s*['\"]?sk-[A-Za-z0-9]{20,}",  # OpenAI
        r"password\s*=\s*['\"][^'\"]{8,}['\"]",  # Passwords
        r"Bearer\s+[A-Za-z0-9\-_]{20,}",  # Bearer tokens
    ]

    found_secrets = []
    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        found_secrets.extend(matches)

    return found_secrets


def main() -> int:
    """Main CLI entry point for doc_updater.

    Returns:
        Exit code: 0 for success, 1 for failure
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Documentation updater - maintains changelog and docstring sync"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if documentation needs update (exit 1 if yes)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify docstrings and check for secrets",
    )
    parser.add_argument(
        "--suggest",
        action="store_true",
        help="Suggest changelog entries for changed files",
    )

    args = parser.parse_args()

    # If no args provided, show example usage
    if not any(vars(args).values()):
        print("=== Documentation Updater Utilities ===\n")

        # Check for changed files
        changed = get_changed_python_files()
        print(f"Changed Python files: {changed or 'None'}\n")

        # Demonstrate changelog management
        manager = ChangelogManager()
        print(f"Changelog location: {manager.changelog_path}")
        print(f"Changelog exists: {manager.changelog_path.exists()}\n")

        # Demonstrate docstring checking
        checker = DocstringChecker()
        success, output = checker.check()
        print(f"Docstring check: {output}")
        return 0

    # --check: Verify documentation is up to date
    if args.check:
        changed_files = get_changed_python_files()
        if not changed_files:
            print("✅ No changes detected in src/")
            return 0

        print(f"⚠️  Detected {len(changed_files)} changed Python files:")
        for file in changed_files:
            print(f"  - {file}")

        # Check if changelog was updated
        try:
            manager = ChangelogManager()
            changelog_content = manager.read_current()

            # Simple heuristic: check if any changed file is mentioned
            files_documented = sum(
                1 for f in changed_files if f in changelog_content
            )

            if files_documented == 0:
                print("\n❌ Changelog may need updating!")
                print("Run with --suggest to see suggested entries")
                return 1
            else:
                print(f"\n✅ {files_documented}/{len(changed_files)} files appear in changelog")
                return 0

        except FileNotFoundError:
            print("❌ Changelog not found!")
            return 1

    # --verify: Check docstrings and secrets
    if args.verify:
        print("=== Verification Report ===\n")
        all_passed = True

        # 1. Check docstrings
        print("1. Docstring Check:")
        checker = DocstringChecker()
        success, output = checker.check()
        print(f"   {output}")
        if not success:
            all_passed = False

        # 2. Check for secrets in staged changes
        print("\n2. Secret Detection:")
        try:
            result = subprocess.run(
                ["git", "diff", "--cached"],
                capture_output=True,
                text=True,
                check=True,
            )
            secrets = detect_secrets_in_content(result.stdout)
            if secrets:
                print(f"   ❌ Potential secrets detected: {len(secrets)} patterns")
                for secret in secrets[:3]:  # Show first 3
                    print(f"      - {secret[:30]}...")
                all_passed = False
            else:
                print("   ✅ No secrets detected in staged changes")

        except subprocess.CalledProcessError:
            print("   ⚠️  Could not check staged changes (not a git repo?)")

        return 0 if all_passed else 1

    # --suggest: Generate changelog suggestions
    if args.suggest:
        changed_files = get_changed_python_files()
        if not changed_files:
            print("✅ No changes detected - no suggestions needed")
            return 0

        print("=== Suggested Changelog Entries ===\n")
        print("## [Unreleased]\n")
        print("### Changed")
        for file in changed_files:
            print(f"- Updated `{file}`")

        print("\n💡 Review and customize these entries in docs/changelog.md")
        return 0

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
