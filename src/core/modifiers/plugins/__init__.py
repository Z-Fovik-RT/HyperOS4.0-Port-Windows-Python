"""Built-in modifier plugins.

This module contains plugins for common modification tasks.
"""

from src.core.modifiers.plugins.eu_localization import EULocalizationPlugin
from src.core.modifiers.plugins.feature_unlock import FeatureUnlockPlugin
from src.core.modifiers.plugins.file_replacement import FileReplacementPlugin
from src.core.modifiers.plugins.vndk_fix import VNDKFixPlugin
from src.core.modifiers.plugins.wild_boost import WildBoostPlugin

__all__ = [
    "WildBoostPlugin",
    "EULocalizationPlugin",
    "FeatureUnlockPlugin",
    "VNDKFixPlugin",
    "FileReplacementPlugin",
]
