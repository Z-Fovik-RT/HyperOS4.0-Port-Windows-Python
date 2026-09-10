"""ROM Modifiers - Backward compatibility module.

DEPRECATED: This module is kept for backward compatibility.
Please use src.core.modifiers package instead.

Example:
    # Old (deprecated):
    from src.core.modifier import SystemModifier
    
    # New (recommended):
    from src.core.modifiers import SystemModifier
"""
import warnings

from src.core.modifiers import (
    FirmwareModifier,
    FrameworkModifier,
    RomModifier,
    SmaliArgs,
    SystemModifier,
)

# Emit deprecation warning
warnings.warn(
    "src.core.modifier is deprecated. Use src.core.modifiers instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = [
    'SmaliArgs',
    'SystemModifier',
    'FrameworkModifier',
    'FirmwareModifier',
    'RomModifier',
]
