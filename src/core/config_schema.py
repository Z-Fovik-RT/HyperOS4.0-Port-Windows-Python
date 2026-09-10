"""
JSON Schema definitions and validation for device configuration files.
Provides schema validation for replacements.json, features.json, and other config files.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Schema for replacements.json
REPLACEMENTS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["replacements"],
    "properties": {
        "replacements": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["description", "type"],
                "properties": {
                    "id": {"type": "string"},
                    "description": {"type": "string"},
                    "type": {
                        "enum": ["unzip_override", "remove_files", "copy_file_internal", "unzip_override_group"]
                    },
                    "source": {"type": "string"},
                    "target": {"type": "string"},
                    "target_base_dir": {"type": "string"},
                    "files": {"type": "array", "items": {"type": "string"}},
                    "removes": {"type": "array", "items": {"type": "string"}},
                    "build_props": {"type": "object"},
                    "merge_strategy": {"enum": ["append", "override", "remove"]},
                    "remove_by_description": {"type": "string"},
                    "depends_on": {"type": "array", "items": {"type": "string"}},
                    # Condition fields
                    "condition": {"type": "object"},
                    "condition_android_version": {"type": "integer"},
                    "condition_port_android_version": {"type": "integer"},
                    "condition_base_android_version_lt": {"type": "integer"},
                    "condition_base_android_version_gte": {"type": "integer"},
                    "condition_port_os_version_incremental_gte": {"type": "string"},
                    "condition_port_is_coloros": {"type": "boolean"},
                    "condition_port_is_coloros_global": {"type": "boolean"},
                    "condition_port_is_oos": {"type": "boolean"},
                    "condition_regionmark": {"oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
                    "condition_not_regionmark": {"type": "string"},
                    "condition_port_rom_version": {"type": "string"},
                    "condition_file_exists": {"type": "string"},
                    "condition_target_exists": {"type": "boolean"},
                    # Group operations
                    "operations": {
                        "type": "array",
                        "items": {"type": "object"}
                    }
                },
                "dependencies": {
                    "unzip_override": ["source"],
                    "remove_files": ["files"],
                    "copy_file_internal": ["source", "target"],
                    "unzip_override_group": ["operations"]
                }
            }
        }
    }
}

# Schema for features.json
FEATURES_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "oplus_feature": {"type": "array", "items": {"type": "string"}},
        "app_feature": {"type": "array", "items": {"type": "string"}},
        "permission_feature": {"type": "array", "items": {"type": "string"}},
        "permission_oplus_feature": {"type": "array", "items": {"type": "string"}},
        "features_remove": {"type": "array", "items": {"type": "string"}},
        "xml_features": {"type": "object"},
        "build_props": {"type": "object"},
        "props_remove": {"type": "array", "items": {"type": "string"}},
        "props_add": {"type": "object"},
        "enable_eu_localization": {"type": "boolean"}
    }
}

# Schema for port_config.json
PORT_CONFIG_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "partition_to_port": {"type": "array", "items": {"type": "string"}},
        "possible_super_list": {"type": "array", "items": {"type": "string"}},
        "repack_with_ext4": {"type": "boolean"},
        "super_extended": {"type": "boolean"},
        "pack_with_dsu": {"type": "boolean"},
        "pack_method": {"type": "string"},
        "ddr_type": {"type": "string"},
        "reusabe_partition_list": {"type": "array", "items": {"type": "string"}},
        "system_dlkm_enabled": {"type": "boolean"},
        "vendor_dlkm_enabled": {"type": "boolean"}
    }
}


class ConfigValidationError(Exception):
    """Exception raised when configuration validation fails."""
    def __init__(self, message: str, errors: List[str]):
        self.message = message
        self.errors = errors
        super().__init__(self.message)


class ConfigValidator:
    """
    Validates configuration files against defined schemas.
    Provides detailed error messages for debugging.
    """
    
    SCHEMA_MAP = {
        "replacements.json": REPLACEMENTS_SCHEMA,
        "features.json": FEATURES_SCHEMA,
        "port_config.json": PORT_CONFIG_SCHEMA
    }
    
    def __init__(self, strict_mode: bool = False):
        """
        Initialize validator.
        
        Args:
            strict_mode: If True, raise exception on validation error.
                        If False, log warnings and continue.
        """
        self.strict_mode = strict_mode
        self.warnings: List[str] = []
    
    def validate(self, config_path: str, config_data: Optional[Dict] = None) -> Tuple[bool, List[str]]:
        """
        Validate a configuration file or data against its schema.
        
        Args:
            config_path: Path to the config file (used to determine schema)
            config_data: Pre-loaded config data (optional, skips file reading)
        
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        path = Path(config_path)
        filename = path.name
        
        if filename not in self.SCHEMA_MAP:
            self.warnings.append(f"No schema defined for {filename}, skipping validation")
            return True, []
        
        schema = self.SCHEMA_MAP[filename]
        
        if config_data is None:
            if not path.exists():
                return False, [f"Config file not found: {config_path}"]
            try:
                with open(path, 'r') as f:
                    config_data = json.load(f)
            except json.JSONDecodeError as e:
                return False, [f"Invalid JSON in {config_path}: {e}"]
        
        errors = self._validate_schema(config_data, schema, path)
        
        if errors and self.strict_mode:
            raise ConfigValidationError(
                f"Validation failed for {config_path}",
                errors
            )
        
        return len(errors) == 0, errors
    
    def _validate_schema(self, data: Any, schema: Dict, path: Path, prefix: str = "") -> List[str]:
        """
        Recursively validate data against schema.
        
        Args:
            data: Data to validate
            schema: Schema to validate against
            path: Path for error messages
            prefix: Property prefix for nested errors
        
        Returns:
            List of error messages
        """
        errors = []
        schema_type = schema.get("type")
        
        # Type validation
        if schema_type == "object":
            if not isinstance(data, dict):
                errors.append(f"{prefix or path}: Expected object, got {type(data).__name__}")
                return errors
            
            # Required fields
            for req in schema.get("required", []):
                if req not in data:
                    errors.append(f"{prefix or path}: Missing required field '{req}'")
            
            # Properties validation
            properties = schema.get("properties", {})
            for key, value in data.items():
                if key in properties:
                    prop_prefix = f"{prefix}.{key}" if prefix else key
                    errors.extend(self._validate_schema(value, properties[key], path, prop_prefix))
                # Unknown fields warning (optional, can be enabled for strict mode)
                # elif self.strict_mode:
                #     errors.append(f"{prefix or path}: Unknown field '{key}'")
        
        elif schema_type == "array":
            if not isinstance(data, list):
                errors.append(f"{prefix or path}: Expected array, got {type(data).__name__}")
                return errors
            
            items_schema = schema.get("items", {})
            for i, item in enumerate(data):
                item_prefix = f"{prefix}[{i}]" if prefix else f"[{i}]"
                errors.extend(self._validate_schema(item, items_schema, path, item_prefix))
        
        elif schema_type == "string":
            if not isinstance(data, str):
                errors.append(f"{prefix or path}: Expected string, got {type(data).__name__}")
        
        elif schema_type == "integer":
            if not isinstance(data, int) or isinstance(data, bool):
                errors.append(f"{prefix or path}: Expected integer, got {type(data).__name__}")
        
        elif schema_type == "boolean":
            if not isinstance(data, bool):
                errors.append(f"{prefix or path}: Expected boolean, got {type(data).__name__}")
        
        elif schema_type == "oneOf":
            # Validate against multiple possible types
            valid = False
            for option in schema.get("oneOf", []):
                test_errors = self._validate_schema(data, option, path, prefix)
                if not test_errors:
                    valid = True
                    break
            if not valid:
                errors.append(f"{prefix or path}: Value does not match any allowed type")
        
        elif schema_type == "enum":
            if data not in schema.get("enum", []):
                errors.append(f"{prefix or path}: Value '{data}' not in allowed values {schema.get('enum')}")
        
        # Dependencies validation
        if isinstance(data, dict) and "dependencies" in schema:
            dependencies = schema["dependencies"]
            for key, required_fields in dependencies.items():
                if data.get("type") == key:
                    for req_field in required_fields:
                        if req_field not in data:
                            errors.append(
                                f"{prefix or path}: Type '{key}' requires field '{req_field}'"
                            )
        
        return errors
    
    def validate_all_configs(self, base_dir: str = "devices") -> Dict[str, Tuple[bool, List[str]]]:
        """
        Validate all configuration files in the devices directory.
        
        Args:
            base_dir: Base directory to search for configs
        
        Returns:
            Dictionary mapping config paths to (is_valid, errors) tuples
        """
        results = {}
        base_path = Path(base_dir)
        
        # Find all JSON files
        for json_file in base_path.rglob("*.json"):
            is_valid, errors = self.validate(str(json_file))
            results[str(json_file)] = (is_valid, errors)
        
        return results


def validate_config(config_path: str, strict: bool = False) -> Tuple[bool, List[str]]:
    """
    Convenience function to validate a single config file.
    
    Args:
        config_path: Path to the config file
        strict: If True, raise exception on error
    
    Returns:
        Tuple of (is_valid, list of error messages)
    """
    validator = ConfigValidator(strict_mode=strict)
    return validator.validate(config_path)


def validate_all_configs(base_dir: str = "devices") -> Dict[str, Tuple[bool, List[str]]]:
    """
    Convenience function to validate all config files.
    
    Args:
        base_dir: Base directory to search for configs
    
    Returns:
        Dictionary mapping config paths to validation results
    """
    validator = ConfigValidator()
    return validator.validate_all_configs(base_dir)
