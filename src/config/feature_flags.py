"""
Feature Flags System.

Provides controlled feature rollout with:
- Percentage-based rollout
- Easy enable/disable
- Consistent behavior per request (using hash)

Architecture Decision: ADR-009

Usage:
    from src.config import FeatureFlags

    # Simple check
    if FeatureFlags.is_enabled("new_feature"):
        use_new_feature()

    # With rollout percentage (consistent per user/request)
    if FeatureFlags.is_enabled_for("new_feature", user_id="user123"):
        use_new_feature()

    # Get flag details
    flag = FeatureFlags.get_flag("new_feature")
    print(flag.description)
"""

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Default config path
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "feature_flags.yaml"


@dataclass
class Flag:
    """Represents a single feature flag."""

    name: str
    enabled: bool
    rollout_percentage: int
    description: str
    experiment_id: str | None = None
    created_date: str | None = None
    owner: str | None = None

    def is_enabled_for_percentage(self, identifier: str) -> bool:
        """Check if flag is enabled for a given identifier (user/request).

        Uses consistent hashing so same identifier always gets same result.

        Args:
            identifier: Unique identifier (user_id, request_id, etc.)

        Returns:
            True if flag should be enabled for this identifier
        """
        if not self.enabled:
            return False

        if self.rollout_percentage >= 100:
            return True

        if self.rollout_percentage <= 0:
            return False

        # Consistent hash based on flag name + identifier
        # Using SHA256 for consistent hashing (not for cryptographic security)
        hash_input = f"{self.name}:{identifier}"
        hash_value = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16)
        percentage = hash_value % 100

        return percentage < self.rollout_percentage


class FeatureFlags:
    """Singleton feature flag manager.

    Loads flags from YAML configuration and provides access methods.
    """

    _instance: "FeatureFlags | None" = None
    _flags: dict[str, Flag] = {}
    _config_path: Path = DEFAULT_CONFIG_PATH
    _loaded: bool = False

    def __new__(cls) -> "FeatureFlags":
        """Create or return the singleton instance.

        Returns:
            The singleton FeatureFlags instance.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def _ensure_loaded(cls) -> None:
        """Ensure flags are loaded from config."""
        if not cls._loaded:
            cls._load()

    @classmethod
    def _load(cls, config_path: Path | None = None) -> None:
        """Load flags from YAML configuration.

        Args:
            config_path: Path to config file (uses default if None)
        """
        path = config_path or cls._config_path

        if not path.exists():
            logger.warning(f"Feature flags config not found: {path}")
            cls._flags = {}
            cls._loaded = True
            return

        try:
            with open(path) as f:
                config = yaml.safe_load(f) or {}

            cls._flags = {}
            for name, data in config.items():
                if isinstance(data, dict):
                    cls._flags[name] = Flag(
                        name=name,
                        enabled=data.get("enabled", False),
                        rollout_percentage=data.get("rollout_percentage", 0),
                        description=data.get("description", ""),
                        experiment_id=data.get("experiment_id"),
                        created_date=data.get("created_date"),
                        owner=data.get("owner"),
                    )

            cls._loaded = True
            logger.info(f"Loaded {len(cls._flags)} feature flags from {path}")

        except Exception as e:
            logger.error(f"Failed to load feature flags: {e}")
            cls._flags = {}
            cls._loaded = True

    @classmethod
    def reload(cls, config_path: Path | None = None) -> None:
        """Force reload of flags from config.

        Args:
            config_path: Path to config file (uses default if None)
        """
        cls._loaded = False
        cls._load(config_path)

    @classmethod
    def is_enabled(cls, flag_name: str, default: bool = False) -> bool:
        """Check if a feature flag is enabled.

        Simple check - returns True if enabled and rollout >= 100%.
        For percentage-based rollout, use is_enabled_for().

        Args:
            flag_name: Name of the flag
            default: Value to return if flag doesn't exist

        Returns:
            True if flag is enabled
        """
        cls._ensure_loaded()

        flag = cls._flags.get(flag_name)
        if flag is None:
            logger.debug(f"Unknown flag: {flag_name}, returning default: {default}")
            return default

        return flag.enabled and flag.rollout_percentage >= 100

    @classmethod
    def is_enabled_for(
        cls,
        flag_name: str,
        identifier: str,
        default: bool = False,
    ) -> bool:
        """Check if a feature flag is enabled for a specific identifier.

        Uses consistent hashing for percentage-based rollout.

        Args:
            flag_name: Name of the flag
            identifier: Unique identifier (user_id, request_id, etc.)
            default: Value to return if flag doesn't exist

        Returns:
            True if flag is enabled for this identifier
        """
        cls._ensure_loaded()

        flag = cls._flags.get(flag_name)
        if flag is None:
            logger.debug(f"Unknown flag: {flag_name}, returning default: {default}")
            return default

        return flag.is_enabled_for_percentage(identifier)

    @classmethod
    def get_flag(cls, flag_name: str) -> Flag | None:
        """Get a flag by name.

        Args:
            flag_name: Name of the flag

        Returns:
            Flag object or None if not found
        """
        cls._ensure_loaded()
        return cls._flags.get(flag_name)

    @classmethod
    def list_flags(cls) -> list[str]:
        """List all flag names."""
        cls._ensure_loaded()
        return list(cls._flags.keys())

    @classmethod
    def get_all_flags(cls) -> dict[str, Flag]:
        """Get all flags."""
        cls._ensure_loaded()
        return cls._flags.copy()

    @classmethod
    def get_enabled_flags(cls) -> list[str]:
        """Get names of all enabled flags (100% rollout)."""
        cls._ensure_loaded()
        return [
            name
            for name, flag in cls._flags.items()
            if flag.enabled and flag.rollout_percentage >= 100
        ]

    @classmethod
    def get_status_summary(cls) -> dict[str, Any]:
        """Get summary of all flags for debugging/monitoring.

        Returns:
            Dict with flag statuses
        """
        cls._ensure_loaded()

        return {
            "total_flags": len(cls._flags),
            "enabled_flags": len(cls.get_enabled_flags()),
            "flags": {
                name: {
                    "enabled": flag.enabled,
                    "rollout": flag.rollout_percentage,
                    "description": flag.description,
                }
                for name, flag in cls._flags.items()
            },
        }


# Convenience function for simple usage
def is_feature_enabled(flag_name: str, default: bool = False) -> bool:
    """Check if a feature is enabled.

    Convenience wrapper around FeatureFlags.is_enabled().

    Args:
        flag_name: Name of the flag
        default: Value if flag doesn't exist

    Returns:
        True if enabled
    """
    return FeatureFlags.is_enabled(flag_name, default)
