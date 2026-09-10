"""Unified modifier system integrating all plugin types."""

from typing import List, Optional

from src.core.config_loader import load_device_config
from src.core.modifiers.base_modifier import BaseModifier
from src.core.modifiers.plugin_system import ModifierPlugin, PluginManager
from src.core.modifiers.plugins import (
    EULocalizationPlugin,
    FeatureUnlockPlugin,
    FileReplacementPlugin,
    VNDKFixPlugin,
    WildBoostPlugin,
)
from src.core.modifiers.plugins.apk import ApkModifierRegistry
from src.core.props import PropertyModifier

BUILTIN_SYSTEM_PLUGINS = (
    FileReplacementPlugin,
    PropertyModifier,
    WildBoostPlugin,
    FeatureUnlockPlugin,
    VNDKFixPlugin,
    EULocalizationPlugin,
)


class UnifiedModifier(BaseModifier):
    """Unified modifier handling both system and APK modifications.

    This provides a single entry point for all ROM modifications:
    - System-level: File replacements, wild_boost, features, etc.
    - APK-level: Individual APK patches (installer, settings, etc.)
    """

    def __init__(
        self,
        context,
        enable_apk_mods: bool = True,
        dry_run: bool = False,
        max_workers: int = 4,
    ):
        super().__init__(context, "UnifiedModifier")

        # System-level plugin manager
        self.system_manager = PluginManager(
            context, self.logger, dry_run=dry_run, max_workers=max_workers
        )

        # APK-level plugin manager
        self.apk_manager = (
            PluginManager(
                context, self.logger, dry_run=dry_run, max_workers=max_workers
            )
            if enable_apk_mods
            else None
        )

        self._register_plugins()

    def _register_plugins(self):
        """Register all default plugins."""
        # Load device config
        if not hasattr(self.ctx, "device_config"):
            self.ctx.device_config = load_device_config(
                getattr(self.ctx, "stock_rom_code", "unknown"), self.logger
            )

        # Register system plugins - auto-discover from src.core.modifiers.plugins package
        self.logger.debug("Auto-discovering system-level plugins...")
        self._auto_discover_system_plugins()

        # Register APK plugins
        if self.apk_manager:
            self.logger.debug("Registering APK-level plugins...")
            ApkModifierRegistry.auto_discover(self.apk_manager)

    def _auto_discover_system_plugins(self):
        """Dynamically discover and register system-level plugins."""
        import importlib
        import pkgutil

        from src.core.modifiers.plugins import __path__ as plugins_path

        # Get the package name
        package_name = "src.core.modifiers.plugins"

        # Discover all modules in the plugins package
        for _, name, _ in pkgutil.iter_modules(plugins_path, prefix=package_name + "."):
            try:
                # Import the module
                module = importlib.import_module(name)

                # Look for classes that inherit from ModifierPlugin
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    # Check if it's a plugin class and has the required attributes
                    if (
                        hasattr(attr, "__module__")
                        and attr.__module__ == name
                        and isinstance(attr, type)
                        and issubclass(attr, ModifierPlugin)
                        and attr != ModifierPlugin
                    ):
                        # Register the plugin class in the system manager
                        try:
                            self.system_manager.register(attr)
                        except Exception as e:
                            self.logger.debug(f"Skipped plugin {attr.__name__}: {e}")

            except ImportError as e:
                self.logger.debug(f"Could not import plugin module {name}: {e}")

        # Explicit defaults are still registered as a safety net, but only when
        # auto-discovery did not already find them.
        for plugin_cls in BUILTIN_SYSTEM_PLUGINS:
            try:
                plugin_name = getattr(
                    plugin_cls,
                    "name",
                    plugin_cls.__name__.lower().replace("plugin", ""),
                )
                if not self.system_manager.has_plugin(plugin_name):
                    self.system_manager.register(plugin_cls)
            except Exception as e:
                self.logger.debug(
                    f"Could not register plugin {plugin_cls.__name__}: {e}"
                )

        # Log registered plugins
        registered_plugins = self.system_manager.list_plugins()
        if len(registered_plugins) == 0:
            self.logger.warning("No plugins registered in system manager")
        else:
            self.logger.debug(
                f"Registered {len(registered_plugins)} system-level plugins: {[p.name for p in registered_plugins]}"
            )

    def run(self, phases: Optional[List[str]] = None) -> bool:
        """Execute all modifications.

        Args:
            phases: Optional list of phases to run ('system', 'apk')
                   If None, runs all phases.

        Returns:
            bool: True if all phases succeeded
        """
        phases = phases or ["system", "apk"]
        all_success = True

        # Phase 1: System-level modifications
        if "system" in phases:
            self.logger.info("=" * 60)
            self.logger.info("PHASE 1: System-Level Modifications")
            self.logger.info("=" * 60)

            self.logger.info("Executing system-level plugins...")
            results = self.system_manager.execute()

            success = sum(1 for r in results.values() if r is True)
            failed = sum(1 for r in results.values() if r is False)
            skipped = sum(1 for r in results.values() if r is None)

            self.logger.info(
                f"System modifications: {success} succeeded, "
                f"{failed} failed, {skipped} skipped"
            )

            if failed > 0:
                all_success = False

        # Phase 2: APK-level modifications
        if "apk" in phases and self.apk_manager:
            self.logger.info("=" * 60)
            self.logger.info("PHASE 2: APK-Level Modifications")
            self.logger.info("=" * 60)

            # Build APK caches for fast lookup
            if hasattr(self.ctx, "build_apk_caches"):
                cache_stats = self.ctx.build_apk_caches()
                self.logger.info(
                    f"APK caches ready: {cache_stats['files']} files, "
                    f"{cache_stats['packages']} packages"
                )

            self.logger.info("Executing APK-level plugins...")
            results = self.apk_manager.execute()

            success = sum(1 for r in results.values() if r is True)
            failed = sum(1 for r in results.values() if r is False)
            skipped = sum(1 for r in results.values() if r is None)

            self.logger.info(
                f"APK modifications: {success} succeeded, "
                f"{failed} failed, {skipped} skipped"
            )

            if failed > 0:
                all_success = False

        return all_success

    def add_system_plugin(self, plugin_class, **kwargs):
        """Add a custom system-level plugin."""
        self.system_manager.register(plugin_class, **kwargs)
        return self

    def add_apk_plugin(self, plugin_class, **kwargs):
        """Add a custom APK-level plugin."""
        if self.apk_manager:
            self.apk_manager.register(plugin_class, **kwargs)
        return self

    def enable_system_plugin(self, name: str, enabled: bool = True):
        """Enable/disable a system plugin."""
        self.system_manager.enable_plugin(name, enabled)
        return self

    def enable_apk_plugin(self, name: str, enabled: bool = True):
        """Enable/disable an APK plugin."""
        if self.apk_manager:
            self.apk_manager.enable_plugin(name, enabled)
        return self

    def list_plugins(self) -> dict:
        """List all registered plugins."""
        return {
            "system": self.system_manager.list_plugins(),
            "apk": self.apk_manager.list_plugins() if self.apk_manager else [],
        }


# Backward compatibility: SystemModifier still works as before
class SystemModifier(BaseModifier):
    """Handles system-level ROM modifications using plugins.

    Note: This is now a thin wrapper around UnifiedModifier for
    backward compatibility. Consider using UnifiedModifier directly.
    """

    def __init__(self, context):
        super().__init__(context, "SystemModifier")
        self._unified = UnifiedModifier(context, enable_apk_mods=False)

    def run(self) -> bool:
        """Execute system modifications."""
        return self._unified.run(phases=["system"])

    def add_plugin(self, plugin_class, **kwargs):
        """Add a custom plugin."""
        self._unified.add_system_plugin(plugin_class, **kwargs)
        return self

    def enable_plugin(self, name: str, enabled: bool = True):
        """Enable/disable a plugin."""
        self._unified.enable_system_plugin(name, enabled)
        return self

    def list_plugins(self):
        """List all registered plugins."""
        return self._unified.list_plugins()["system"]


class ApkModifier(BaseModifier):
    """Handles APK-level modifications using plugins.

    This is a standalone APK modifier that can be used independently
    or as part of UnifiedModifier.
    """

    def __init__(self, context, dry_run: bool = False, max_workers: int = 4):
        super().__init__(context, "ApkModifier")
        self.plugin_manager = PluginManager(
            context, self.logger, dry_run=dry_run, max_workers=max_workers
        )
        self._register_plugins()

    def _register_plugins(self):
        """Register APK modification plugins."""
        ApkModifierRegistry.auto_discover(self.plugin_manager)

    def run(self) -> bool:
        """Execute all APK modifications."""
        self.logger.info("Starting APK Modifications...")

        results = self.plugin_manager.execute()

        success = sum(1 for r in results.values() if r is True)
        failed = sum(1 for r in results.values() if r is False)
        skipped = sum(1 for r in results.values() if r is None)

        self.logger.info(
            f"APK Modifications Completed: "
            f"{success} succeeded, {failed} failed, {skipped} skipped"
        )

        return failed == 0

    def add_plugin(self, plugin_class, **kwargs):
        """Add a custom APK plugin."""
        self.plugin_manager.register(plugin_class, **kwargs)
        return self

    def enable_plugin(self, name: str, enabled: bool = True):
        """Enable/disable an APK plugin."""
        self.plugin_manager.enable_plugin(name, enabled)
        return self

    def list_plugins(self):
        """List all registered APK plugins."""
        return self.plugin_manager.list_plugins()
