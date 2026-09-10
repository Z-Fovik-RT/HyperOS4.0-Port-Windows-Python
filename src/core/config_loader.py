import json
import logging
from pathlib import Path
from typing import Any, Optional, cast


class ConfigMerger:
    """
    Configuration merger for device-specific settings.
    Merges configurations from common -> device layers with deep merge support.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger("ConfigMerger")

    def deep_merge(
        self, base: dict[str, Any], override: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Deep merge two dictionaries. Override values take precedence.

        Args:
            base: Base dictionary
            override: Dictionary with values to override

        Returns:
            Merged dictionary
        """
        result = base.copy()

        for key, value in override.items():
            if key.startswith("_"):
                # Skip metadata keys (like _comment)
                continue

            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self.deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def load_config(self, config_path: Path) -> dict[str, Any]:
        """Load a single configuration file."""
        if not config_path.exists():
            return {}

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            if isinstance(config_data, dict):
                return cast(dict[str, Any], config_data)
            self.logger.error(
                f"Config root in {config_path} is not an object: {type(config_data).__name__}"
            )
            return {}
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse {config_path}: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Failed to load {config_path}: {e}")
            return {}

    def load_device_config(self, device_codename: str) -> dict[str, Any]:
        """
        Load and merge configuration for a specific device.
        Hierarchy: common -> device

        Args:
            device_codename: Device codename (e.g., 'mayfly', 'fuxi')

        Returns:
            Merged configuration dictionary
        """
        devices_dir = Path("devices")

        # Load common config
        common_config = self.load_config(devices_dir / "common" / "config.json")
        if common_config:
            self.logger.info("Loaded common config.")

        # Load device-specific config
        device_config = self.load_config(devices_dir / device_codename / "config.json")
        if device_config:
            self.logger.info(f"Loaded device config for {device_codename}.")

        # Merge configurations
        merged = self.deep_merge(common_config, device_config)

        # Log summary
        self._log_config_summary(merged, device_codename)

        return merged

    def _log_config_summary(self, config: dict[str, Any], device_codename: str):
        """Log configuration summary."""
        wild_boost = config.get("wild_boost", {})
        pack = config.get("pack", {})
        ksu = config.get("ksu", {})

        self.logger.info(f"Configuration for {device_codename}:")
        self.logger.info(f"  Wild Boost: enabled={wild_boost.get('enable', False)}")
        self.logger.info(
            f"  Pack: type={pack.get('type', 'payload')}, "
            f"fs_type={pack.get('fs_type', 'erofs')}"
        )
        self.logger.info(f"  KSU: enabled={ksu.get('enable', False)}")


def load_device_config(
    device_codename: str, logger: Optional[logging.Logger] = None
) -> dict[str, Any]:
    """
    Convenience function to create a new ConfigMerger and load device configuration.
    This avoids the global singleton and ties configuration to the specific task context.

    Args:
        device_codename: Device codename
        logger: Optional logger instance

    Returns:
        Merged configuration dictionary
    """
    merger = ConfigMerger(logger)
    return merger.load_device_config(device_codename)


# Maintain backward compatibility while moving to per-task configuration
# Global registry for task-specific mergers
_config_merger_instances_registry: dict[str, ConfigMerger] = {}


def load_device_config_with_context(
    task_context: str, device_codename: str, logger: Optional[logging.Logger] = None
) -> dict[str, Any]:
    """
    Load device configuration for a specific task context to avoid cross-contamination.

    Args:
        task_context: Unique identifier for the task (e.g., 'device123_port')
        device_codename: Device codename
        logger: Optional logger instance

    Returns:
        Merged configuration dictionary
    """
    # Create a new ConfigMerger instance for the specific context to avoid conflicts
    merger = ConfigMerger(logger)
    _config_merger_instances_registry[task_context] = merger
    return merger.load_device_config(device_codename)


def get_config_merger(logger: Optional[logging.Logger] = None) -> ConfigMerger:
    """
    DEPRECATED: Create a new ConfigMerger instance.
    Use load_device_config() instead for simple cases or attach ConfigMerger to your context directly.

    Args:
        logger: Optional logger instance

    Returns:
        New ConfigMerger instance
    """
    import warnings

    warnings.warn(
        "get_config_merger() is deprecated. Use load_device_config() directly or "
        "attach ConfigMerger to your context object.",
        DeprecationWarning,
        stacklevel=2,
    )
    return ConfigMerger(logger)
