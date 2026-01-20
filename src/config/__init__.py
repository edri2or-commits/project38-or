"""
Configuration module.

Provides access to feature flags and other configuration.

Usage:
    from src.config import FeatureFlags

    if FeatureFlags.is_enabled("new_feature"):
        # Use new feature
        pass
    else:
        # Use old behavior
        pass
"""

from src.config.feature_flags import FeatureFlags

__all__ = ["FeatureFlags"]
