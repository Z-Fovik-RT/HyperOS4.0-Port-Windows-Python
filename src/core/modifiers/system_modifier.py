"""System-level modifications using plugin architecture."""

from src.core.config_loader import load_device_config
from src.core.modifiers.base_modifier import BaseModifier
from src.core.modifiers.plugin_system import PluginManager
from src.core.modifiers.plugins import (
    EULocalizationPlugin,
    FeatureUnlockPlugin,
    FileReplacementPlugin,
    VNDKFixPlugin,
    WildBoostPlugin,
)


class SystemModifier(BaseModifier):
    """Handles system-level ROM modifications using plugins."""

    def __init__(self, context):
        super().__init__(context, "SystemModifier")
        self.plugin_manager = PluginManager(context, self.logger)
        self._register_default_plugins()
    
    def _register_default_plugins(self):
        """Register built-in system modification plugins."""
        # Load device config if available
        if not hasattr(self.ctx, 'device_config'):
            self.ctx.device_config = load_device_config(
                getattr(self.ctx, 'stock_rom_code', 'unknown'), 
                self.logger
            )
        
        # Register plugins in order of priority
        self.plugin_manager.register(FileReplacementPlugin)
        self.plugin_manager.register(WildBoostPlugin)
        self.plugin_manager.register(FeatureUnlockPlugin)
        self.plugin_manager.register(VNDKFixPlugin)
        self.plugin_manager.register(EULocalizationPlugin)
    
    def run(self):
        """Execute all system modifications via plugins."""
        self.logger.info("Starting System Modification...")
        
        # Execute all registered plugins
        results = self.plugin_manager.execute()
        
        # Log summary
        success_count = sum(1 for r in results.values() if r is True)
        failed_count = sum(1 for r in results.values() if r is False)
        skipped_count = sum(1 for r in results.values() if r is None)
        
        self.logger.info(
            f"System Modification Completed: "
            f"{success_count} succeeded, {failed_count} failed, {skipped_count} skipped"
        )
        
        return failed_count == 0
    
    def add_plugin(self, plugin_class, **kwargs):
        """Add a custom plugin to the system modifier.
        
        Example:
            modifier.add_plugin(MyCustomPlugin, custom_param="value")
        """
        self.plugin_manager.register(plugin_class, **kwargs)
        return self
    
    def enable_plugin(self, name: str, enabled: bool = True):
        """Enable or disable a specific plugin."""
        self.plugin_manager.enable_plugin(name, enabled)
        return self
    
    def list_plugins(self):
        """List all registered plugins."""
        return self.plugin_manager.list_plugins()


# Backward compatibility - provide a simplified interface
class SimpleSystemModifier(BaseModifier):
    """Simplified system modifier for basic use cases.
    
    This is a compatibility wrapper that runs the most common
    system modifications without the full plugin system.
    """
    
    def __init__(self, context):
        super().__init__(context, "SimpleSystemModifier")
        self.modifier = SystemModifier(context)
    
    def run(self):
        """Run system modifications."""
        return self.modifier.run()
