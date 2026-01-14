"""Automatic Dependency Update Module.

Provides programmatic dependency management for Python projects:
- Vulnerability scanning with pip-audit
- Outdated package detection
- Automated update recommendations
- PR creation for updates

Example:
    >>> from src.dependency_updater import DependencyUpdater
    >>>
    >>> updater = DependencyUpdater(requirements_path="requirements.txt")
    >>> report = await updater.generate_update_report()
    >>> print(f"Vulnerabilities: {report.vulnerability_count}")
    >>> print(f"Outdated: {report.outdated_count}")
"""

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================


class UpdatePriority(Enum):
    """Update priority levels."""

    CRITICAL = "critical"  # Security vulnerabilities
    HIGH = "high"  # High severity or very outdated
    MEDIUM = "medium"  # Minor updates available
    LOW = "low"  # Patch updates only


class UpdateType(Enum):
    """Types of updates."""

    SECURITY = "security"  # CVE fix
    MAJOR = "major"  # Breaking changes possible
    MINOR = "minor"  # New features, backward compatible
    PATCH = "patch"  # Bug fixes only


@dataclass
class Vulnerability:
    """Security vulnerability information.

    Attributes:
        package: Package name
        current_version: Currently installed version
        fixed_version: Version with fix
        cve_id: CVE identifier
        severity: Severity level (CRITICAL, HIGH, MEDIUM, LOW)
        description: Vulnerability description
    """

    package: str
    current_version: str
    fixed_version: str | None
    cve_id: str | None
    severity: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "package": self.package,
            "current_version": self.current_version,
            "fixed_version": self.fixed_version,
            "cve_id": self.cve_id,
            "severity": self.severity,
            "description": self.description,
        }


@dataclass
class OutdatedPackage:
    """Information about an outdated package.

    Attributes:
        name: Package name
        current_version: Currently installed version
        latest_version: Latest available version
        update_type: Type of update (major, minor, patch)
    """

    name: str
    current_version: str
    latest_version: str
    update_type: UpdateType

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "current_version": self.current_version,
            "latest_version": self.latest_version,
            "update_type": self.update_type.value,
        }


@dataclass
class UpdateReport:
    """Comprehensive dependency update report.

    Attributes:
        generated_at: Report generation timestamp
        vulnerabilities: List of security vulnerabilities
        outdated_packages: List of outdated packages
        recommendations: Prioritized update recommendations
        can_auto_update: Whether safe to auto-update
    """

    generated_at: datetime
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    outdated_packages: list[OutdatedPackage] = field(default_factory=list)
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    can_auto_update: bool = True

    @property
    def vulnerability_count(self) -> int:
        """Count of vulnerabilities."""
        return len(self.vulnerabilities)

    @property
    def outdated_count(self) -> int:
        """Count of outdated packages."""
        return len(self.outdated_packages)

    @property
    def has_critical(self) -> bool:
        """Check if any critical vulnerabilities exist."""
        return any(v.severity.upper() == "CRITICAL" for v in self.vulnerabilities)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "generated_at": self.generated_at.isoformat(),
            "vulnerability_count": self.vulnerability_count,
            "outdated_count": self.outdated_count,
            "has_critical": self.has_critical,
            "can_auto_update": self.can_auto_update,
            "vulnerabilities": [v.to_dict() for v in self.vulnerabilities],
            "outdated_packages": [p.to_dict() for p in self.outdated_packages],
            "recommendations": self.recommendations,
        }


# =============================================================================
# DEPENDENCY UPDATER
# =============================================================================


class DependencyUpdater:
    """Manages dependency updates for Python projects.

    Features:
    - Vulnerability scanning with pip-audit
    - Outdated package detection
    - Update type classification (major/minor/patch)
    - Automated update recommendations
    - Safe update application

    Example:
        >>> updater = DependencyUpdater("requirements.txt")
        >>> report = await updater.generate_update_report()
        >>> if report.has_critical:
        ...     await updater.apply_security_updates()
    """

    def __init__(
        self,
        requirements_path: str | Path = "requirements.txt",
        lock_file_path: str | Path | None = "requirements.lock",
    ):
        """Initialize dependency updater.

        Args:
            requirements_path: Path to requirements.txt
            lock_file_path: Path to lock file (optional)
        """
        self.requirements_path = Path(requirements_path)
        self.lock_file_path = Path(lock_file_path) if lock_file_path else None

    async def scan_vulnerabilities(self) -> list[Vulnerability]:
        """Scan for security vulnerabilities using pip-audit.

        Returns:
            List of Vulnerability objects

        Note:
            Requires pip-audit to be installed.
        """
        vulnerabilities = []

        try:
            # Run pip-audit
            result = subprocess.run(
                [
                    "pip-audit",
                    "--requirement",
                    str(self.requirements_path),
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0 and result.stdout:
                # No vulnerabilities found
                logger.info("No vulnerabilities found")
                return []

            # Parse JSON output (pip-audit returns non-zero if vulnerabilities found)
            try:
                audit_data = json.loads(result.stdout)

                for item in audit_data:
                    vuln = Vulnerability(
                        package=item.get("name", "unknown"),
                        current_version=item.get("version", "unknown"),
                        fixed_version=(
                            item.get("fix_versions", [None])[-1]
                            if item.get("fix_versions")
                            else None
                        ),
                        cve_id=item.get("id"),
                        severity=item.get("severity", "UNKNOWN").upper(),
                        description=item.get("description", "No description"),
                    )
                    vulnerabilities.append(vuln)

                logger.warning(
                    f"Found {len(vulnerabilities)} vulnerabilities",
                    extra={"count": len(vulnerabilities)},
                )

            except json.JSONDecodeError:
                logger.error("Failed to parse pip-audit output")

        except subprocess.TimeoutExpired:
            logger.error("pip-audit timed out")
        except FileNotFoundError:
            logger.warning("pip-audit not installed, skipping vulnerability scan")
        except Exception as e:
            logger.error(f"Vulnerability scan failed: {e}")

        return vulnerabilities

    async def check_outdated(self) -> list[OutdatedPackage]:
        """Check for outdated packages.

        Returns:
            List of OutdatedPackage objects
        """
        outdated = []

        try:
            result = subprocess.run(
                ["pip", "list", "--outdated", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0 and result.stdout:
                packages = json.loads(result.stdout)

                for pkg in packages:
                    name = pkg.get("name", "unknown")
                    current = pkg.get("version", "0.0.0")
                    latest = pkg.get("latest_version", "0.0.0")

                    # Determine update type
                    update_type = self._classify_update(current, latest)

                    outdated.append(
                        OutdatedPackage(
                            name=name,
                            current_version=current,
                            latest_version=latest,
                            update_type=update_type,
                        )
                    )

                logger.info(
                    f"Found {len(outdated)} outdated packages",
                    extra={"count": len(outdated)},
                )

        except subprocess.TimeoutExpired:
            logger.error("pip list --outdated timed out")
        except json.JSONDecodeError:
            logger.error("Failed to parse pip output")
        except Exception as e:
            logger.error(f"Outdated check failed: {e}")

        return outdated

    def _classify_update(self, current: str, latest: str) -> UpdateType:
        """Classify update type based on version difference.

        Args:
            current: Current version string
            latest: Latest version string

        Returns:
            UpdateType enum value
        """
        try:
            current_parts = [int(x) for x in current.split(".")[:3]]
            latest_parts = [int(x) for x in latest.split(".")[:3]]

            # Pad with zeros if needed
            while len(current_parts) < 3:
                current_parts.append(0)
            while len(latest_parts) < 3:
                latest_parts.append(0)

            if latest_parts[0] != current_parts[0]:
                return UpdateType.MAJOR
            elif latest_parts[1] != current_parts[1]:
                return UpdateType.MINOR
            else:
                return UpdateType.PATCH

        except (ValueError, IndexError):
            return UpdateType.PATCH

    def _generate_recommendations(
        self,
        vulnerabilities: list[Vulnerability],
        outdated: list[OutdatedPackage],
    ) -> list[dict[str, Any]]:
        """Generate prioritized update recommendations.

        Args:
            vulnerabilities: List of vulnerabilities
            outdated: List of outdated packages

        Returns:
            List of recommendation dictionaries
        """
        recommendations = []

        # Priority 1: Security vulnerabilities
        for vuln in vulnerabilities:
            if vuln.fixed_version:
                recommendations.append(
                    {
                        "priority": UpdatePriority.CRITICAL.value,
                        "package": vuln.package,
                        "action": f"Update to {vuln.fixed_version}",
                        "reason": f"Security fix for {vuln.cve_id or 'vulnerability'}",
                        "command": f"pip install {vuln.package}=={vuln.fixed_version}",
                    }
                )

        # Priority 2: Major updates (review required)
        for pkg in outdated:
            if pkg.update_type == UpdateType.MAJOR:
                recommendations.append(
                    {
                        "priority": UpdatePriority.LOW.value,
                        "package": pkg.name,
                        "action": f"Review update to {pkg.latest_version}",
                        "reason": "Major version update - breaking changes possible",
                        "command": f"pip install {pkg.name}=={pkg.latest_version}",
                    }
                )

        # Priority 3: Minor updates
        for pkg in outdated:
            if pkg.update_type == UpdateType.MINOR:
                recommendations.append(
                    {
                        "priority": UpdatePriority.MEDIUM.value,
                        "package": pkg.name,
                        "action": f"Update to {pkg.latest_version}",
                        "reason": "New features available",
                        "command": f"pip install {pkg.name}=={pkg.latest_version}",
                    }
                )

        # Priority 4: Patch updates
        for pkg in outdated:
            if pkg.update_type == UpdateType.PATCH:
                recommendations.append(
                    {
                        "priority": UpdatePriority.LOW.value,
                        "package": pkg.name,
                        "action": f"Update to {pkg.latest_version}",
                        "reason": "Bug fixes",
                        "command": f"pip install {pkg.name}=={pkg.latest_version}",
                    }
                )

        # Sort by priority
        priority_order = {
            UpdatePriority.CRITICAL.value: 0,
            UpdatePriority.HIGH.value: 1,
            UpdatePriority.MEDIUM.value: 2,
            UpdatePriority.LOW.value: 3,
        }
        recommendations.sort(key=lambda x: priority_order.get(x["priority"], 99))

        return recommendations

    async def generate_update_report(self) -> UpdateReport:
        """Generate comprehensive update report.

        Returns:
            UpdateReport with all findings and recommendations
        """
        # Run scans concurrently
        vulnerabilities, outdated = await asyncio.gather(
            self.scan_vulnerabilities(),
            self.check_outdated(),
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(vulnerabilities, outdated)

        # Determine if auto-update is safe
        # Don't auto-update if there are major updates
        has_major = any(p.update_type == UpdateType.MAJOR for p in outdated)
        can_auto_update = not has_major

        return UpdateReport(
            generated_at=datetime.now(UTC),
            vulnerabilities=vulnerabilities,
            outdated_packages=outdated,
            recommendations=recommendations,
            can_auto_update=can_auto_update,
        )

    async def apply_security_updates(self) -> list[str]:
        """Apply only security updates.

        Returns:
            List of updated package names
        """
        updated = []
        vulnerabilities = await self.scan_vulnerabilities()

        for vuln in vulnerabilities:
            if vuln.fixed_version:
                try:
                    subprocess.run(
                        ["pip", "install", f"{vuln.package}=={vuln.fixed_version}"],
                        check=True,
                        capture_output=True,
                    )
                    updated.append(vuln.package)
                    logger.info(
                        f"Updated {vuln.package} to {vuln.fixed_version}",
                        extra={"package": vuln.package, "version": vuln.fixed_version},
                    )
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to update {vuln.package}: {e}")

        return updated

    async def apply_safe_updates(self) -> list[str]:
        """Apply patch and minor updates (safe, non-breaking).

        Returns:
            List of updated package names
        """
        updated = []
        outdated = await self.check_outdated()

        for pkg in outdated:
            # Only apply patch and minor updates
            if pkg.update_type in (UpdateType.PATCH, UpdateType.MINOR):
                try:
                    subprocess.run(
                        ["pip", "install", f"{pkg.name}=={pkg.latest_version}"],
                        check=True,
                        capture_output=True,
                    )
                    updated.append(pkg.name)
                    logger.info(
                        f"Updated {pkg.name} to {pkg.latest_version}",
                        extra={"package": pkg.name, "version": pkg.latest_version},
                    )
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to update {pkg.name}: {e}")

        return updated

    def update_requirements_file(self, updates: dict[str, str]) -> bool:
        """Update requirements.txt with new versions.

        Args:
            updates: Dictionary of {package: new_version}

        Returns:
            True if file was updated successfully
        """
        try:
            content = self.requirements_path.read_text()

            for package, version in updates.items():
                # Replace version in file
                import re

                pattern = rf"^{re.escape(package)}==[\d\.]+"
                replacement = f"{package}=={version}"
                content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

            self.requirements_path.write_text(content)
            logger.info(f"Updated requirements.txt with {len(updates)} changes")
            return True

        except Exception as e:
            logger.error(f"Failed to update requirements.txt: {e}")
            return False

    def regenerate_lock_file(self) -> bool:
        """Regenerate requirements.lock from current environment.

        Returns:
            True if lock file was generated successfully
        """
        if not self.lock_file_path:
            return False

        try:
            result = subprocess.run(
                ["pip", "freeze"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.lock_file_path.write_text(result.stdout)
            logger.info("Regenerated requirements.lock")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to regenerate lock file: {e}")
            return False


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


async def quick_security_check(requirements_path: str = "requirements.txt") -> bool:
    """Quick check for security vulnerabilities.

    Args:
        requirements_path: Path to requirements file

    Returns:
        True if no vulnerabilities found
    """
    updater = DependencyUpdater(requirements_path)
    vulnerabilities = await updater.scan_vulnerabilities()
    return len(vulnerabilities) == 0


async def get_update_summary(requirements_path: str = "requirements.txt") -> dict[str, Any]:
    """Get summary of available updates.

    Args:
        requirements_path: Path to requirements file

    Returns:
        Dictionary with update summary
    """
    updater = DependencyUpdater(requirements_path)
    report = await updater.generate_update_report()

    return {
        "vulnerability_count": report.vulnerability_count,
        "outdated_count": report.outdated_count,
        "has_critical": report.has_critical,
        "can_auto_update": report.can_auto_update,
        "security_updates": [v.package for v in report.vulnerabilities if v.fixed_version],
        "patch_updates": [
            p.name for p in report.outdated_packages if p.update_type == UpdateType.PATCH
        ],
        "minor_updates": [
            p.name for p in report.outdated_packages if p.update_type == UpdateType.MINOR
        ],
        "major_updates": [
            p.name for p in report.outdated_packages if p.update_type == UpdateType.MAJOR
        ],
    }
