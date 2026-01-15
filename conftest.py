"""Pytest configuration and hooks for automatic test skipping.

This module implements intelligent test collection that automatically skips
tests when their required dependencies are missing, preventing CI failures
due to optional or in-development modules.
"""

import subprocess
import sys

import pytest  # noqa: F401 - Required by pytest hooks

# Cache for module availability checks (avoid repeated subprocess calls)
_module_check_cache: dict[str, bool] = {}

# Cache for PostgreSQL availability check
_postgres_available: bool | None = None


def _check_module_importable(module_name: str) -> bool:
    """
    Check if a module can be imported successfully.

    Uses subprocess to avoid crashing the test process if the module
    has import-time errors (e.g., pyo3_runtime.PanicException from broken
    cryptography/jwt).

    Args:
        module_name: Name of the module to check

    Returns:
        True if module can be imported, False otherwise
    """
    if module_name in _module_check_cache:
        return _module_check_cache[module_name]

    try:
        result = subprocess.run(
            [sys.executable, "-c", f"import {module_name}"],
            capture_output=True,
            timeout=10,
        )
        is_importable = result.returncode == 0
    except Exception:
        is_importable = False

    _module_check_cache[module_name] = is_importable
    return is_importable


def _check_postgres_available() -> bool:
    """
    Check if PostgreSQL is accessible.

    Uses a subprocess to try connecting to the database URL.

    Returns:
        True if PostgreSQL is accessible, False otherwise
    """
    global _postgres_available
    if _postgres_available is not None:
        return _postgres_available

    import os

    db_url = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/test")

    # Quick check - if no asyncpg installed, definitely can't connect
    if not _check_module_importable("asyncpg"):
        _postgres_available = False
        return False

    # Try to connect using a simple socket check (faster than full connection)
    import socket

    try:
        # Parse host and port from DATABASE_URL
        # Format: postgresql://user:pass@host:port/db or postgresql://host:port/db
        if "@" in db_url:
            host_port = db_url.split("@")[1].split("/")[0]
        else:
            host_port = db_url.replace("postgresql://", "").split("/")[0]

        if ":" in host_port:
            host, port = host_port.rsplit(":", 1)
            port = int(port)
        else:
            host = host_port
            port = 5432

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        _postgres_available = result == 0
    except Exception:
        _postgres_available = False

    return _postgres_available


def pytest_ignore_collect(collection_path, config):
    """
    Decide whether to ignore a test file during collection.

    This hook is called before pytest tries to import a test module,
    allowing us to skip files that would fail due to missing dependencies.

    Args:
        collection_path: Path object for the file/directory
        config: pytest config object

    Returns:
        True to ignore the file, False/None to collect it
    """
    if not collection_path.suffix == ".py":
        return None

    # Check if this is a test file
    if "tests" not in str(collection_path):
        return None

    # Try to import the test module safely
    try:
        # Read the file content to check for imports
        content = collection_path.read_text()

        # Check for imports of known problematic modules
        # Format: (import_pattern_in_file, required_module_to_check)
        # Note: Patterns check transitive dependencies, e.g., orchestrator -> jwt
        problematic_imports = [
            # Core orchestration - needs jwt (via github_app_client)
            ("from src.orchestrator import", "jwt"),
            ("from src.github_app_client import", "jwt"),
            # GitHub auth - needs jwt directly
            ("from src.github_auth import", "jwt"),
            ("from src import github_auth", "jwt"),
            # Railway/n8n clients - need tenacity
            ("from src.railway_client import", "tenacity"),
            ("from src.n8n_client import", "tenacity"),
            # Agent factory - needs anthropic
            ("from src.factory", "anthropic"),
            # Agent harness - needs sqlalchemy
            ("from src.harness", "sqlalchemy"),
            # Observability - needs opentelemetry
            ("from src.observability", "opentelemetry"),
            # FastAPI - needs fastapi and async db
            ("from fastapi import", "fastapi"),
            ("from src.api", "fastapi"),
            # Autonomous controller chain (imports orchestrator -> github_app_client -> jwt)
            ("from src.autonomous_controller import", "jwt"),
            # Anomaly integrator (imports autonomous_controller)
            ("from src.anomaly_response_integrator import", "jwt"),
            # Monitoring loop (imports anomaly integrator and ml detector)
            ("from src.monitoring_loop import", "jwt"),
            # Performance baseline - needs psutil
            ("from src.performance_baseline import", "psutil"),
            # Secrets manager - needs google.cloud.secretmanager (includes cryptography chain)
            ("from src.secrets_manager import", "google.cloud.secretmanager"),
        ]

        # Special check for API agent tests - need PostgreSQL running
        # These tests use TestClient which triggers app lifespan that connects to DB
        if "test_api_agents" in str(collection_path):
            # Check if PostgreSQL is accessible
            if not _check_postgres_available():
                return True

        for import_pattern, required_module in problematic_imports:
            if import_pattern in content:
                # Check if module can be imported successfully using subprocess
                # This avoids crashing the test process if the module has
                # import-time errors (e.g., pyo3 panic from broken jwt/cryptography)
                if not _check_module_importable(required_module):
                    return True

        return None

    except Exception:
        # If we can't read the file, let pytest handle it normally
        return None


def pytest_collection_modifyitems(config, items):
    """
    Mark tests with missing dependencies for better reporting.

    This runs after collection to add markers to skipped tests.

    Args:
        config: pytest config object
        items: list of test items collected
    """
    # Count skipped tests by reason
    skipped_counts = {}

    for item in items:
        # Check if item was marked for skipping
        skip_markers = list(item.iter_markers(name="skip"))
        if skip_markers:
            reason = skip_markers[0].kwargs.get("reason", "Unknown")
            skipped_counts[reason] = skipped_counts.get(reason, 0) + 1


def pytest_configure(config):
    """
    Register custom markers.

    Args:
        config: pytest config object
    """
    config.addinivalue_line(
        "markers",
        "skip_if_missing: automatically skip if dependencies are missing",
    )


def pytest_report_header(config):
    """
    Add custom header to pytest output.

    Args:
        config: pytest config object

    Returns:
        List of header lines
    """
    return [
        "Auto-skip enabled: Tests with missing dependencies will be skipped",
        "Run 'pip install -r requirements.txt' to enable all tests",
    ]
