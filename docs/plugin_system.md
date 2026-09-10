# Plugin System Documentation

## Overview

The ROM modification system now supports a flexible plugin architecture that allows:
- **Modular modifications**: Each feature is a separate plugin
- **Easy extension**: Add new modifications without modifying core code
- **Conditional execution**: Plugins check prerequisites before running
- **Dependency management**: Plugins can depend on others
- **Priority-based ordering**: Control execution order

## Architecture

```
┌─────────────────────────────────────────┐
│           SystemModifier                │
│  (Coordinates system-level mods)        │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│          PluginManager                  │
│  (Manages plugin lifecycle)             │
└──────────────────┬──────────────────────┘
                   │
       ┌───────────┼───────────┐
       ▼           ▼           ▼
  ┌────────┐  ┌────────┐  ┌────────┐
  │Plugin 1 │  │Plugin 2  │  │Plugin 3  │
  │(wild    │  │(file     │  │(vndk     │
  │boost)   │  │replace)  │  │fix)      │ 
  └────────┘  └────────┘  └────── ──┘
```

## Built-in Plugins

### FileReplacementPlugin
- **Name**: `file_replacement`
- **Priority**: 20
- **Purpose**: Execute file/directory replacements from replacements.json

### WildBoostPlugin
- **Name**: `wild_boost`
- **Priority**: 10
- **Purpose**: Install wild_boost kernel modules and device spoofing
- **Prerequisites**: wild_boost.enable = true in config

### FeatureUnlockPlugin
- **Name**: `feature_unlock`
- **Priority**: 30
- **Purpose**: Unlock device features from features.json
- **Dependencies**: Runs after wild_boost

### VNDKFixPlugin
- **Name**: `vndk_fix`
- **Priority**: 40
- **Purpose**: Fix VNDK APEX and VINTF manifest

### EULocalizationPlugin
- **Name**: `eu_localization`
- **Priority**: 50
- **Purpose**: Apply EU localization bundle
- **Prerequisites**: is_port_eu_rom and eu_bundle must be set

## Usage

### Basic Usage

```python
from src.core.modifiers import SystemModifier

# Create modifier (auto-registers default plugins)
modifier = SystemModifier(ctx)

# Run all plugins
modifier.run()
```

### Custom Plugin

```python
from src.core.modifiers import ModifierPlugin, ModifierRegistry

@ModifierRegistry.register
class MyCustomPlugin(ModifierPlugin):
    name = "my_custom"
    description = "My custom modification"
    priority = 25
    
    def modify(self) -> bool:
        # Your modification logic
        target_dir = self.ctx.target_dir
        # ... do work ...
        return True
```

### Advanced: Custom Plugin Manager

```python
from src.core.modifiers import PluginManager
from src.core.modifiers.plugins import FileReplacementPlugin

# Create custom manager
manager = PluginManager(ctx)

# Register specific plugins
manager.register(FileReplacementPlugin)
manager.register(MyCustomPlugin)

# Add hooks
manager.add_hook('pre_modify', lambda p: print(f"Starting {p.name}"))
manager.add_hook('post_modify', lambda p, s: print(f"Done: {s}"))

# Execute
results = manager.execute()
```

## Plugin Priority Guide

| Priority Range | Purpose | Examples |
|---------------|---------|----------|
| 0-10 | Critical system setup | wild_boost kernel modules |
| 11-20 | File operations | replacements, file copying |
| 21-40 | System configuration | feature unlock, VNDK fix |
| 41-60 | Localization & UI | EU localization, themes |
| 61-100 | Optional/Custom | User extensions, debug plugins |

## API Reference

### ModifierPlugin

Base class for all plugins.

**Attributes:**
- `name` (str): Plugin identifier
- `description` (str): Human-readable description
- `version` (str): Plugin version
- `priority` (int): Execution order (lower = earlier)
- `dependencies` (list): Names of required plugins

**Methods:**
- `modify() -> bool`: Main modification logic
- `check_prerequisites() -> bool`: Validate before running
- `get_config(key, default) -> Any`: Access device config

### PluginManager

Manages plugin registration and execution.

**Methods:**
- `register(plugin_class, **kwargs) -> PluginManager`: Register a plugin
- `unregister(name) -> bool`: Remove a plugin
- `execute(plugin_names=None) -> Dict[str, bool]`: Run plugins
- `enable_plugin(name, enabled=True) -> bool`: Toggle plugin
- `add_hook(event, callback) -> PluginManager`: Add hook
- `list_plugins() -> List[ModifierPlugin]`: Get all plugins

### ModifierRegistry

Global registry for plugin discovery.

**Methods:**
- `register(plugin_class)`: Decorator to auto-register
- `get(name) -> Optional[Type[ModifierPlugin]]`: Get by name
- `list_all() -> Dict[str, Type]`: Get all registered

## Migration Guide

### From Old System

Old code:
```python
from src.core.modifier import SystemModifier
modifier = SystemModifier(ctx)
modifier.run()
```

New code (same API, plugin-based internally):
```python
from src.core.modifiers import SystemModifier
modifier = SystemModifier(ctx)
modifier.run()
```

### Adding Custom Logic

Old: Modify SystemModifier methods
New: Create a plugin

```python
class MyLogicPlugin(ModifierPlugin):
    name = "my_logic"
    priority = 35
    
    def modify(self) -> bool:
        # Your logic here
        return True

# Register and run
modifier = SystemModifier(ctx)
modifier.add_plugin(MyLogicPlugin)
modifier.run()
```

## Best Practices

1. **Keep plugins focused**: One plugin = one feature
2. **Check prerequisites**: Use `check_prerequisites()` for validation
3. **Handle errors gracefully**: Return False on failure, don't raise
4. **Use appropriate priority**: Consider dependencies when setting priority
5. **Document clearly**: Provide name, description, and purpose
6. **Test independently**: Each plugin should be testable in isolation

## Examples

See `examples/modifier_plugins_example.py` for complete examples.
