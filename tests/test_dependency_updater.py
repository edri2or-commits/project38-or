"""Tests for Automatic Dependency Update Module.

Tests cover:
- Vulnerability scanning
- Outdated package detection
- Update classification
- Recommendation generation
- Report generation
"""

import sys
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest


def _setup_google_mocks():
    """Set up Google module mocks if not already present."""
    modules_to_mock = [
        "google",
        "google.api_core",
        "google.api_core.exceptions",
        "google.cloud",
        "google.cloud.secretmanager",
    ]
    originals = {}
    for mod in modules_to_mock:
        originals[mod] = sys.modules.get(mod)
        if originals[mod] is None:
            sys.modules[mod] = MagicMock()
    return originals


def _restore_google_mocks(originals):
    """Restore Google module mocks."""
    for mod, original in originals.items():
        if original is not None:
            sys.modules[mod] = original


# Set up mocks at import time (needed for imports)
_google_mock_originals = _setup_google_mocks()


@pytest.fixture(scope="module", autouse=True)
def ensure_google_mocks():
    """Ensure Google mocks are set up and cleaned up properly."""
    yield
    _restore_google_mocks(_google_mock_originals)


from src.dependency_updater import (  # noqa: E402
    DependencyUpdater,
    OutdatedPackage,
    UpdatePriority,
    UpdateReport,
    UpdateType,
    Vulnerability,
    get_update_summary,
    quick_security_check,
)

# =============================================================================
# VULNERABILITY TESTS
# =============================================================================


class TestVulnerability:
    """Tests for Vulnerability dataclass."""

    def test_vulnerability_creation(self):
        """Test creating a vulnerability object."""
        vuln = Vulnerability(
            package="requests",
            current_version="2.28.0",
            fixed_version="2.31.0",
            cve_id="CVE-2023-32681",
            severity="CRITICAL",
            description="Proxy-Authorization header leak",
        )

        assert vuln.package == "requests"
        assert vuln.current_version == "2.28.0"
        assert vuln.fixed_version == "2.31.0"
        assert vuln.cve_id == "CVE-2023-32681"

    def test_vulnerability_to_dict(self):
        """Test vulnerability serialization."""
        vuln = Vulnerability(
            package="requests",
            current_version="2.28.0",
            fixed_version="2.31.0",
            cve_id="CVE-2023-32681",
            severity="CRITICAL",
            description="Test vulnerability",
        )

        data = vuln.to_dict()

        assert data["package"] == "requests"
        assert data["fixed_version"] == "2.31.0"
        assert data["severity"] == "CRITICAL"


# =============================================================================
# OUTDATED PACKAGE TESTS
# =============================================================================


class TestOutdatedPackage:
    """Tests for OutdatedPackage dataclass."""

    def test_outdated_package_creation(self):
        """Test creating an outdated package object."""
        pkg = OutdatedPackage(
            name="fastapi",
            current_version="0.100.0",
            latest_version="0.104.1",
            update_type=UpdateType.MINOR,
        )

        assert pkg.name == "fastapi"
        assert pkg.update_type == UpdateType.MINOR

    def test_outdated_package_to_dict(self):
        """Test outdated package serialization."""
        pkg = OutdatedPackage(
            name="fastapi",
            current_version="0.100.0",
            latest_version="0.104.1",
            update_type=UpdateType.MINOR,
        )

        data = pkg.to_dict()

        assert data["name"] == "fastapi"
        assert data["update_type"] == "minor"


# =============================================================================
# UPDATE REPORT TESTS
# =============================================================================


class TestUpdateReport:
    """Tests for UpdateReport dataclass."""

    def test_empty_report(self):
        """Test report with no vulnerabilities or updates."""
        report = UpdateReport(generated_at=datetime.now(UTC))

        assert report.vulnerability_count == 0
        assert report.outdated_count == 0
        assert report.has_critical is False
        assert report.can_auto_update is True

    def test_report_with_critical(self):
        """Test report with critical vulnerability."""
        report = UpdateReport(
            generated_at=datetime.now(UTC),
            vulnerabilities=[
                Vulnerability(
                    package="requests",
                    current_version="2.28.0",
                    fixed_version="2.31.0",
                    cve_id="CVE-2023-32681",
                    severity="CRITICAL",
                    description="Test",
                )
            ],
        )

        assert report.vulnerability_count == 1
        assert report.has_critical is True

    def test_report_to_dict(self):
        """Test report serialization."""
        report = UpdateReport(
            generated_at=datetime.now(UTC),
            outdated_packages=[
                OutdatedPackage(
                    name="pytest",
                    current_version="7.4.0",
                    latest_version="7.4.3",
                    update_type=UpdateType.PATCH,
                )
            ],
        )

        data = report.to_dict()

        assert "generated_at" in data
        assert data["vulnerability_count"] == 0
        assert data["outdated_count"] == 1


# =============================================================================
# UPDATE TYPE CLASSIFICATION TESTS
# =============================================================================


class TestUpdateClassification:
    """Tests for update type classification."""

    @pytest.fixture
    def updater(self, tmp_path):
        """Create updater with temp requirements file."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.31.0\n")
        return DependencyUpdater(req_file)

    def test_classify_major_update(self, updater):
        """Test major version update classification."""
        result = updater._classify_update("1.0.0", "2.0.0")
        assert result == UpdateType.MAJOR

    def test_classify_minor_update(self, updater):
        """Test minor version update classification."""
        result = updater._classify_update("1.0.0", "1.1.0")
        assert result == UpdateType.MINOR

    def test_classify_patch_update(self, updater):
        """Test patch version update classification."""
        result = updater._classify_update("1.0.0", "1.0.1")
        assert result == UpdateType.PATCH

    def test_classify_complex_version(self, updater):
        """Test classification with complex versions."""
        result = updater._classify_update("1.2.3", "2.0.0")
        assert result == UpdateType.MAJOR

        result = updater._classify_update("1.2.3", "1.3.0")
        assert result == UpdateType.MINOR

        result = updater._classify_update("1.2.3", "1.2.4")
        assert result == UpdateType.PATCH


# =============================================================================
# RECOMMENDATION GENERATION TESTS
# =============================================================================


class TestRecommendations:
    """Tests for recommendation generation."""

    @pytest.fixture
    def updater(self, tmp_path):
        """Create updater with temp requirements file."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.31.0\n")
        return DependencyUpdater(req_file)

    def test_security_recommendations_first(self, updater):
        """Test that security fixes are prioritized."""
        vulnerabilities = [
            Vulnerability(
                package="requests",
                current_version="2.28.0",
                fixed_version="2.31.0",
                cve_id="CVE-2023-32681",
                severity="CRITICAL",
                description="Test",
            )
        ]
        outdated = [
            OutdatedPackage(
                name="pytest",
                current_version="7.4.0",
                latest_version="7.4.3",
                update_type=UpdateType.PATCH,
            )
        ]

        recs = updater._generate_recommendations(vulnerabilities, outdated)

        assert recs[0]["priority"] == UpdatePriority.CRITICAL.value
        assert recs[0]["package"] == "requests"

    def test_empty_recommendations(self, updater):
        """Test recommendations with no issues."""
        recs = updater._generate_recommendations([], [])
        assert len(recs) == 0

    def test_major_updates_low_priority(self, updater):
        """Test that major updates are low priority."""
        outdated = [
            OutdatedPackage(
                name="pytest",
                current_version="7.0.0",
                latest_version="8.0.0",
                update_type=UpdateType.MAJOR,
            )
        ]

        recs = updater._generate_recommendations([], outdated)

        assert recs[0]["priority"] == UpdatePriority.LOW.value
        assert "Review" in recs[0]["action"]


# =============================================================================
# DEPENDENCY UPDATER TESTS
# =============================================================================


class TestDependencyUpdater:
    """Tests for DependencyUpdater class."""

    @pytest.fixture
    def updater(self, tmp_path):
        """Create updater with temp requirements file."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.31.0\nfastapi==0.100.0\n")
        return DependencyUpdater(req_file)

    @pytest.mark.asyncio
    async def test_scan_vulnerabilities_no_pip_audit(self, updater):
        """Test vulnerability scan when pip-audit not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = await updater.scan_vulnerabilities()

            assert result == []

    @pytest.mark.asyncio
    async def test_scan_vulnerabilities_clean(self, updater):
        """Test vulnerability scan with no issues."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="[]",
            )

            result = await updater.scan_vulnerabilities()

            assert result == []

    @pytest.mark.asyncio
    async def test_check_outdated(self, updater):
        """Test checking for outdated packages."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='[{"name": "requests", "version": "2.28.0", "latest_version": "2.31.0"}]',
            )

            result = await updater.check_outdated()

            assert len(result) == 1
            assert result[0].name == "requests"
            assert result[0].latest_version == "2.31.0"

    @pytest.mark.asyncio
    async def test_generate_update_report(self, updater):
        """Test generating full update report."""
        with (
            patch.object(updater, "scan_vulnerabilities", return_value=[]),
            patch.object(
                updater,
                "check_outdated",
                return_value=[
                    OutdatedPackage(
                        name="pytest",
                        current_version="7.4.0",
                        latest_version="7.4.3",
                        update_type=UpdateType.PATCH,
                    )
                ],
            ),
        ):
            report = await updater.generate_update_report()

            assert report.vulnerability_count == 0
            assert report.outdated_count == 1
            assert report.can_auto_update is True

    def test_update_requirements_file(self, updater, tmp_path):
        """Test updating requirements file."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.28.0\nfastapi==0.100.0\n")
        updater.requirements_path = req_file

        result = updater.update_requirements_file({"requests": "2.31.0"})

        assert result is True
        content = req_file.read_text()
        assert "requests==2.31.0" in content


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================


class TestHelperFunctions:
    """Tests for helper functions."""

    @pytest.mark.asyncio
    async def test_quick_security_check_clean(self, tmp_path):
        """Test quick security check with no vulnerabilities."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.31.0\n")

        with patch.object(DependencyUpdater, "scan_vulnerabilities", return_value=[]):
            result = await quick_security_check(str(req_file))

            assert result is True

    @pytest.mark.asyncio
    async def test_get_update_summary(self, tmp_path):
        """Test getting update summary."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.31.0\n")

        with patch.object(
            DependencyUpdater,
            "generate_update_report",
            return_value=UpdateReport(
                generated_at=datetime.now(UTC),
                outdated_packages=[
                    OutdatedPackage(
                        name="pytest",
                        current_version="7.4.0",
                        latest_version="7.4.3",
                        update_type=UpdateType.PATCH,
                    )
                ],
            ),
        ):
            summary = await get_update_summary(str(req_file))

            assert summary["vulnerability_count"] == 0
            assert summary["outdated_count"] == 1
            assert "pytest" in summary["patch_updates"]


# =============================================================================
# UPDATE TYPE ENUM TESTS
# =============================================================================


class TestUpdateTypeEnum:
    """Tests for UpdateType enum."""

    def test_update_type_values(self):
        """Test UpdateType enum values."""
        assert UpdateType.SECURITY.value == "security"
        assert UpdateType.MAJOR.value == "major"
        assert UpdateType.MINOR.value == "minor"
        assert UpdateType.PATCH.value == "patch"


class TestUpdatePriorityEnum:
    """Tests for UpdatePriority enum."""

    def test_update_priority_values(self):
        """Test UpdatePriority enum values."""
        assert UpdatePriority.CRITICAL.value == "critical"
        assert UpdatePriority.HIGH.value == "high"
        assert UpdatePriority.MEDIUM.value == "medium"
        assert UpdatePriority.LOW.value == "low"
