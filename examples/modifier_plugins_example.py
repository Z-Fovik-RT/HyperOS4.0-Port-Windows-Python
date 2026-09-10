"""Example: Creating custom modifier plugins.

This example shows how to extend the ROM modification system with custom plugins.
"""
from pathlib import Path

from src.core.modifiers import (
    ModifierPlugin,
    ModifierRegistry,
    SystemModifier,
)


# Method 1: Create a simple custom plugin
class CustomThemePlugin(ModifierPlugin):
    """Custom plugin to apply themes."""
    
    name = "custom_theme"
    description = "Apply custom theme resources"
    priority = 25  # Run after file replacement (20) but before wild_boost (10)
    
    def modify(self) -> bool:
        """Apply custom theme."""
        self.logger.info("Applying custom theme...")
        
        # Example: Copy theme files
        theme_dir = Path("themes/my_custom_theme")
        if theme_dir.exists():
            # Copy theme resources
            self.logger.info(f"Copying theme from {theme_dir}")
            # ... implementation
        
        return True


# Method 2: Plugin with configuration
class SignatureBypassPlugin(ModifierPlugin):
    """Plugin to apply signature bypass patches."""
    
    name = "signature_bypass"
    description = "Apply signature bypass to specific APKs"
    priority = 35
    dependencies = ["file_replacement"]  # Must run after file replacement
    
    def check_prerequisites(self) -> bool:
        """Check if signature bypass is enabled in config."""
        return self.get_config("signature_bypass", {}).get("enable", False)
    
    def modify(self) -> bool:
        """Apply signature bypass."""
        config = self.get_config("signature_bypass", {})
        target_apks = config.get("target_apks", [])
        
        for apk_name in target_apks:
            self.logger.info(f"Applying signature bypass to {apk_name}")
            # ... implementation
        
        return True


# Method 3: Using the registry decorator
@ModifierRegistry.register
class AutoRegisterPlugin(ModifierPlugin):
    """Plugin that auto-registers via decorator."""
    
    name = "auto_register_demo"
    description = "Demonstrates auto-registration"
    priority = 100
    
    def modify(self) -> bool:
        self.logger.info("Auto-registered plugin executed!")
        return True


# Usage examples
def example_basic_usage(ctx):
    """Basic plugin usage."""
    
    # Create system modifier (auto-registers default plugins)
    modifier = SystemModifier(ctx)
    
    # Add custom plugin
    modifier.add_plugin(CustomThemePlugin)
    
    # Run all plugins
    modifier.run()


def example_plugin_management(ctx):
    """Advanced plugin management."""
    
    modifier = SystemModifier(ctx)
    
    # List all plugins
    plugins = modifier.list_plugins()
    for plugin in plugins:
        print(f"Plugin: {plugin.name} (priority={plugin.priority})")
    
    # Disable specific plugin
    modifier.enable_plugin("eu_localization", enabled=False)
    
    # Enable only specific plugins
    # modifier.plugin_manager.execute(["wild_boost", "vndk_fix"])


def example_custom_modifier_with_plugins(ctx):
    """Creating a custom modifier with specific plugins."""
    from src.core.modifiers import PluginManager
    from src.core.modifiers.plugins import FileReplacementPlugin
    
    # Create custom plugin manager
    manager = PluginManager(ctx)
    
    # Register only specific plugins
    manager.register(FileReplacementPlugin)
    manager.register(CustomThemePlugin)
    
    # Add hooks
    def on_plugin_start(plugin):
        print(f"Starting: {plugin.name}")
    
    def on_plugin_complete(plugin, success):
        status = "✓" if success else "✗"
        print(f"Completed: {plugin.name} {status}")
    
    manager.add_hook('pre_modify', on_plugin_start)
    manager.add_hook('post_modify', on_plugin_complete)
    
    # Execute
    results = manager.execute()
    
    return results


# Plugin development tips
PLUGIN_DEVELOPMENT_GUIDE = """
# Plugin Development Guide

## 1. Creating a Plugin

```python
from src.core.modifiers import ModifierPlugin

class MyPlugin(ModifierPlugin):
    name = "my_plugin"
    description = "What this plugin does"
    priority = 50
    dependencies = ["other_plugin"]  # Optional
    
    def check_prerequisites(self) -> bool:
        # Return False to skip this plugin
        return True
    
    def modify(self) -> bool:
        # Main modification logic
        target_dir = self.ctx.target_dir
        # ... do work ...
        return True  # Success
```

## 2. Accessing Context

Plugins have access to the PortingContext via `self.ctx`:
- `self.ctx.target_dir` - Target ROM directory
- `self.ctx.stock` - Stock ROM package
- `self.ctx.port` - Port ROM package
- `self.ctx.stock_rom_code` - Device code

## 3. Configuration

Use `self.get_config(key, default)` to access device config:

```python
def modify(self) -> bool:
    enabled = self.get_config("my_feature", {}).get("enable", False)
    if not enabled:
        return True  # Skip gracefully
    # ...
```

## 4. Priority System

Lower priority = earlier execution:
- 10-20: Critical system modifications
- 30-50: Standard modifications
- 70-100: Optional/custom modifications

## 5. Error Handling

Plugins should handle errors gracefully:

```python
def modify(self) -> bool:
    try:
        # ... risky operation ...
        return True
    except Exception as e:
        self.logger.error(f"Failed: {e}")
        return False  # Continue with other plugins
```

## 6. Hooks

Register hooks to observe plugin execution:

```python
manager.add_hook('pre_modify', lambda p: print(f"Starting {p.name}"))
manager.add_hook('post_modify', lambda p, s: print(f"Done {p.name}: {s}"))
manager.add_hook('on_error', lambda p, e: print(f"Error in {p.name}: {e}"))
```
"""

if __name__ == "__main__":
    print("Plugin System Examples")
    print("=" * 50)
    print(PLUGIN_DEVELOPMENT_GUIDE)
