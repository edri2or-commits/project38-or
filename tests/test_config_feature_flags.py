"""Tests for src/config/feature_flags.py - Feature Flags System."""

import tempfile
from pathlib import Path

import pytest

# Skip all tests if yaml not installed
pytest.importorskip("yaml")


class TestFlagDataclass:
    """Tests for Flag dataclass."""

    def test_flag_import(self):
        """Flag should be importable."""
        from src.config.feature_flags import Flag

        assert Flag is not None

    def test_flag_required_fields(self):
        """Flag should require name, enabled, rollout_percentage, description."""
        from src.config.feature_flags import Flag

        flag = Flag(
            name="test_feature",
            enabled=True,
            rollout_percentage=100,
            description="Test feature",
        )
        assert flag.name == "test_feature"
        assert flag.enabled is True
        assert flag.rollout_percentage == 100
        assert flag.description == "Test feature"

    def test_flag_optional_fields(self):
        """Flag should have optional fields with None defaults."""
        from src.config.feature_flags import Flag

        flag = Flag(
            name="test",
            enabled=False,
            rollout_percentage=0,
            description="Test",
        )
        assert flag.experiment_id is None
        assert flag.created_date is None
        assert flag.owner is None

    def test_flag_custom_optional_fields(self):
        """Flag should accept custom optional fields."""
        from src.config.feature_flags import Flag

        flag = Flag(
            name="test",
            enabled=True,
            rollout_percentage=50,
            description="Test",
            experiment_id="exp_001",
            created_date="2026-01-15",
            owner="test@example.com",
        )
        assert flag.experiment_id == "exp_001"
        assert flag.created_date == "2026-01-15"
        assert flag.owner == "test@example.com"


class TestFlagPercentageRollout:
    """Tests for Flag.is_enabled_for_percentage method."""

    def test_disabled_flag_returns_false(self):
        """Disabled flag should return False regardless of identifier."""
        from src.config.feature_flags import Flag

        flag = Flag(
            name="test",
            enabled=False,
            rollout_percentage=100,
            description="Test",
        )
        assert flag.is_enabled_for_percentage("user123") is False

    def test_zero_rollout_returns_false(self):
        """Zero rollout should return False for all identifiers."""
        from src.config.feature_flags import Flag

        flag = Flag(
            name="test",
            enabled=True,
            rollout_percentage=0,
            description="Test",
        )
        assert flag.is_enabled_for_percentage("user123") is False
        assert flag.is_enabled_for_percentage("any_user") is False

    def test_full_rollout_returns_true(self):
        """100% rollout should return True for all identifiers."""
        from src.config.feature_flags import Flag

        flag = Flag(
            name="test",
            enabled=True,
            rollout_percentage=100,
            description="Test",
        )
        assert flag.is_enabled_for_percentage("user1") is True
        assert flag.is_enabled_for_percentage("user2") is True
        assert flag.is_enabled_for_percentage("any_id") is True

    def test_consistent_hashing(self):
        """Same identifier should always get same result."""
        from src.config.feature_flags import Flag

        flag = Flag(
            name="test",
            enabled=True,
            rollout_percentage=50,
            description="Test",
        )
        user_id = "consistent_user_123"

        # Call multiple times, should always return same result
        results = [flag.is_enabled_for_percentage(user_id) for _ in range(10)]
        assert all(r == results[0] for r in results)

    def test_different_identifiers_vary(self):
        """Different identifiers should have varied distribution."""
        from src.config.feature_flags import Flag

        flag = Flag(
            name="test",
            enabled=True,
            rollout_percentage=50,
            description="Test",
        )

        # With 50% rollout, ~half should be True
        results = [flag.is_enabled_for_percentage(f"user_{i}") for i in range(100)]
        true_count = sum(results)

        # Should be roughly 50% (allow 30-70 range for randomness)
        assert 30 <= true_count <= 70

    def test_flag_name_affects_hashing(self):
        """Different flag names should produce different results for same identifier."""
        from src.config.feature_flags import Flag

        flag1 = Flag(name="feature_a", enabled=True, rollout_percentage=50, description="A")
        flag2 = Flag(name="feature_b", enabled=True, rollout_percentage=50, description="B")

        user_id = "test_user"

        # With same identifier but different flags, at least some should differ
        results_a = [flag1.is_enabled_for_percentage(f"user_{i}") for i in range(100)]
        results_b = [flag2.is_enabled_for_percentage(f"user_{i}") for i in range(100)]

        # Results should not be identical
        assert results_a != results_b


class TestFeatureFlagsClass:
    """Tests for FeatureFlags singleton class."""

    def test_feature_flags_import(self):
        """FeatureFlags should be importable."""
        from src.config.feature_flags import FeatureFlags

        assert FeatureFlags is not None

    def test_feature_flags_singleton(self):
        """FeatureFlags should be a singleton."""
        from src.config.feature_flags import FeatureFlags

        instance1 = FeatureFlags()
        instance2 = FeatureFlags()
        assert instance1 is instance2

    def test_has_class_methods(self):
        """FeatureFlags should have expected class methods."""
        from src.config.feature_flags import FeatureFlags

        assert hasattr(FeatureFlags, "is_enabled")
        assert hasattr(FeatureFlags, "is_enabled_for")
        assert hasattr(FeatureFlags, "get_flag")
        assert hasattr(FeatureFlags, "list_flags")
        assert hasattr(FeatureFlags, "reload")


class TestFeatureFlagsLoading:
    """Tests for FeatureFlags config loading."""

    def test_load_missing_config(self):
        """Loading missing config should result in empty flags."""
        from src.config.feature_flags import FeatureFlags

        # Reset state
        FeatureFlags._loaded = False
        FeatureFlags._flags = {}

        # Load from non-existent path
        FeatureFlags._load(Path("/nonexistent/path.yaml"))

        assert FeatureFlags._loaded is True
        assert FeatureFlags._flags == {}

    def test_load_valid_config(self):
        """Loading valid config should populate flags."""
        from src.config.feature_flags import FeatureFlags

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
test_feature:
  enabled: true
  rollout_percentage: 100
  description: "Test feature"

disabled_feature:
  enabled: false
  rollout_percentage: 0
  description: "Disabled"
""")
            f.flush()

            FeatureFlags._loaded = False
            FeatureFlags._flags = {}
            FeatureFlags._load(Path(f.name))

            assert "test_feature" in FeatureFlags._flags
            assert "disabled_feature" in FeatureFlags._flags
            assert FeatureFlags._flags["test_feature"].enabled is True
            assert FeatureFlags._flags["disabled_feature"].enabled is False

    def test_reload_clears_cache(self):
        """reload should clear and reload flags."""
        from src.config.feature_flags import FeatureFlags

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
new_feature:
  enabled: true
  rollout_percentage: 50
  description: "New"
""")
            f.flush()

            FeatureFlags._loaded = True
            FeatureFlags._flags = {"old": None}

            FeatureFlags.reload(Path(f.name))

            assert "new_feature" in FeatureFlags._flags
            assert "old" not in FeatureFlags._flags


class TestFeatureFlagsIsEnabled:
    """Tests for FeatureFlags.is_enabled method."""

    def test_is_enabled_true(self):
        """is_enabled should return True for fully enabled flag."""
        from src.config.feature_flags import FeatureFlags, Flag

        FeatureFlags._loaded = True
        FeatureFlags._flags = {
            "enabled_flag": Flag(
                name="enabled_flag",
                enabled=True,
                rollout_percentage=100,
                description="Test",
            )
        }

        assert FeatureFlags.is_enabled("enabled_flag") is True

    def test_is_enabled_false_disabled(self):
        """is_enabled should return False for disabled flag."""
        from src.config.feature_flags import FeatureFlags, Flag

        FeatureFlags._loaded = True
        FeatureFlags._flags = {
            "disabled_flag": Flag(
                name="disabled_flag",
                enabled=False,
                rollout_percentage=100,
                description="Test",
            )
        }

        assert FeatureFlags.is_enabled("disabled_flag") is False

    def test_is_enabled_false_zero_rollout(self):
        """is_enabled should return False for zero rollout."""
        from src.config.feature_flags import FeatureFlags, Flag

        FeatureFlags._loaded = True
        FeatureFlags._flags = {
            "zero_rollout": Flag(
                name="zero_rollout",
                enabled=True,
                rollout_percentage=0,
                description="Test",
            )
        }

        assert FeatureFlags.is_enabled("zero_rollout") is False

    def test_is_enabled_unknown_flag_default(self):
        """is_enabled should return default for unknown flag."""
        from src.config.feature_flags import FeatureFlags

        FeatureFlags._loaded = True
        FeatureFlags._flags = {}

        assert FeatureFlags.is_enabled("unknown") is False
        assert FeatureFlags.is_enabled("unknown", default=True) is True


class TestFeatureFlagsIsEnabledFor:
    """Tests for FeatureFlags.is_enabled_for method."""

    def test_is_enabled_for_uses_percentage(self):
        """is_enabled_for should use percentage-based rollout."""
        from src.config.feature_flags import FeatureFlags, Flag

        FeatureFlags._loaded = True
        FeatureFlags._flags = {
            "partial": Flag(
                name="partial",
                enabled=True,
                rollout_percentage=50,
                description="Test",
            )
        }

        # Should use consistent hashing
        result1 = FeatureFlags.is_enabled_for("partial", "user123")
        result2 = FeatureFlags.is_enabled_for("partial", "user123")
        assert result1 == result2  # Consistent

    def test_is_enabled_for_unknown_flag(self):
        """is_enabled_for should return default for unknown flag."""
        from src.config.feature_flags import FeatureFlags

        FeatureFlags._loaded = True
        FeatureFlags._flags = {}

        assert FeatureFlags.is_enabled_for("unknown", "user123") is False
        assert FeatureFlags.is_enabled_for("unknown", "user123", default=True) is True


class TestFeatureFlagsGetFlag:
    """Tests for FeatureFlags.get_flag method."""

    def test_get_flag_exists(self):
        """get_flag should return Flag object if exists."""
        from src.config.feature_flags import FeatureFlags, Flag

        test_flag = Flag(name="test", enabled=True, rollout_percentage=100, description="Test")
        FeatureFlags._loaded = True
        FeatureFlags._flags = {"test": test_flag}

        result = FeatureFlags.get_flag("test")
        assert result is test_flag

    def test_get_flag_not_exists(self):
        """get_flag should return None if flag doesn't exist."""
        from src.config.feature_flags import FeatureFlags

        FeatureFlags._loaded = True
        FeatureFlags._flags = {}

        result = FeatureFlags.get_flag("nonexistent")
        assert result is None


class TestFeatureFlagsListFlags:
    """Tests for FeatureFlags.list_flags method."""

    def test_list_flags_empty(self):
        """list_flags should return empty list when no flags."""
        from src.config.feature_flags import FeatureFlags

        FeatureFlags._loaded = True
        FeatureFlags._flags = {}

        assert FeatureFlags.list_flags() == []

    def test_list_flags_returns_names(self):
        """list_flags should return flag names."""
        from src.config.feature_flags import FeatureFlags, Flag

        FeatureFlags._loaded = True
        FeatureFlags._flags = {
            "flag_a": Flag(name="flag_a", enabled=True, rollout_percentage=100, description="A"),
            "flag_b": Flag(name="flag_b", enabled=False, rollout_percentage=0, description="B"),
        }

        names = FeatureFlags.list_flags()
        assert "flag_a" in names
        assert "flag_b" in names


class TestFeatureFlagsGetAllFlags:
    """Tests for FeatureFlags.get_all_flags method."""

    def test_get_all_flags_returns_copy(self):
        """get_all_flags should return a copy of flags dict."""
        from src.config.feature_flags import FeatureFlags, Flag

        original = {"test": Flag(name="test", enabled=True, rollout_percentage=100, description="Test")}
        FeatureFlags._loaded = True
        FeatureFlags._flags = original

        result = FeatureFlags.get_all_flags()

        # Should be equal but not the same object
        assert result == original
        assert result is not FeatureFlags._flags


class TestFeatureFlagsGetEnabledFlags:
    """Tests for FeatureFlags.get_enabled_flags method."""

    def test_get_enabled_flags_filters(self):
        """get_enabled_flags should return only fully enabled flags."""
        from src.config.feature_flags import FeatureFlags, Flag

        FeatureFlags._loaded = True
        FeatureFlags._flags = {
            "enabled": Flag(name="enabled", enabled=True, rollout_percentage=100, description="E"),
            "partial": Flag(name="partial", enabled=True, rollout_percentage=50, description="P"),
            "disabled": Flag(name="disabled", enabled=False, rollout_percentage=100, description="D"),
        }

        enabled = FeatureFlags.get_enabled_flags()
        assert "enabled" in enabled
        assert "partial" not in enabled  # Not 100%
        assert "disabled" not in enabled


class TestFeatureFlagsGetStatusSummary:
    """Tests for FeatureFlags.get_status_summary method."""

    def test_get_status_summary_structure(self):
        """get_status_summary should return proper structure."""
        from src.config.feature_flags import FeatureFlags, Flag

        FeatureFlags._loaded = True
        FeatureFlags._flags = {
            "test": Flag(name="test", enabled=True, rollout_percentage=50, description="Test feature")
        }

        summary = FeatureFlags.get_status_summary()

        assert "total_flags" in summary
        assert "enabled_flags" in summary
        assert "flags" in summary
        assert summary["total_flags"] == 1

    def test_get_status_summary_flag_details(self):
        """get_status_summary should include flag details."""
        from src.config.feature_flags import FeatureFlags, Flag

        FeatureFlags._loaded = True
        FeatureFlags._flags = {
            "test": Flag(name="test", enabled=True, rollout_percentage=75, description="My feature")
        }

        summary = FeatureFlags.get_status_summary()

        assert "test" in summary["flags"]
        assert summary["flags"]["test"]["enabled"] is True
        assert summary["flags"]["test"]["rollout"] == 75
        assert summary["flags"]["test"]["description"] == "My feature"


class TestIsFeatureEnabledFunction:
    """Tests for is_feature_enabled convenience function."""

    def test_is_feature_enabled_import(self):
        """is_feature_enabled should be importable."""
        from src.config.feature_flags import is_feature_enabled

        assert is_feature_enabled is not None

    def test_is_feature_enabled_delegates(self):
        """is_feature_enabled should delegate to FeatureFlags.is_enabled."""
        from src.config.feature_flags import FeatureFlags, Flag, is_feature_enabled

        FeatureFlags._loaded = True
        FeatureFlags._flags = {
            "test": Flag(name="test", enabled=True, rollout_percentage=100, description="Test")
        }

        assert is_feature_enabled("test") is True
        assert is_feature_enabled("unknown") is False
        assert is_feature_enabled("unknown", default=True) is True
