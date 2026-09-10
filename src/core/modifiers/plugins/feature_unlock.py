"""Feature unlock plugin.

This plugin unlocks device features based on JSON configuration.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict

from src.core.modifiers.plugin_system import ModifierPlugin, ModifierRegistry


@ModifierRegistry.register
class FeatureUnlockPlugin(ModifierPlugin):
    """Plugin to unlock device features."""

    name = "feature_unlock"
    description = "Unlock device features based on JSON configuration"
    priority = 30

    def modify(self) -> bool:
        """Unlock device features."""
        self.logger.info("Unlocking device features...")

        config = self._load_config()
        if not config:
            return True

        # Check wild_boost dependency
        wild_boost_enabled = self.get_config("wild_boost", {}).get("enable", False)

        # Apply XML features
        xml_features = config.get("xml_features", {})
        if not wild_boost_enabled:
            xml_features = {
                k: v for k, v in xml_features.items() if not k.startswith("support_wild_boost")
            }

        if xml_features:
            self._apply_xml_features(xml_features)

        # Apply build properties
        build_props = config.get("build_props", {})
        if build_props:
            self._apply_build_props(build_props, wild_boost_enabled)

        # Apply EU localization props
        if config.get("enable_eu_localization", False) or getattr(
            self.ctx, "is_port_eu_rom", False
        ):
            self._apply_eu_localization_props()

        return True

    def _load_config(self) -> Dict:
        """Load feature configuration."""
        config = {}

        # Load common config
        common_cfg = Path("devices/common/features.json")
        if common_cfg.exists():
            try:
                with open(common_cfg, "r") as f:
                    config = json.load(f)
            except Exception as e:
                self.logger.error(f"Failed to load common features: {e}")

        # Load device-specific config
        device_cfg = Path(f"devices/{self.ctx.stock_rom_code}/features.json")
        if device_cfg.exists():
            try:
                with open(device_cfg, "r") as f:
                    device_config = json.load(f)

                # Deep merge
                for key, value in device_config.items():
                    if isinstance(value, dict) and key in config:
                        if key == "build_props" and "product" in value and "product" in config[key]:
                            config[key]["product"].update(value["product"])
                        else:
                            config[key].update(value)
                    else:
                        config[key] = value
            except Exception as e:
                self.logger.error(f"Failed to load device features: {e}")

        return config

    def _apply_xml_features(self, features: Dict[str, Any]):
        """Apply XML feature flags."""
        feat_dir = self.ctx.target_dir / "product/etc/device_features"
        if not feat_dir.exists():
            return

        xml_file = feat_dir / f"{self.ctx.stock_rom_code}.xml"
        if not xml_file.exists():
            try:
                xml_file = next(feat_dir.glob("*.xml"))
            except StopIteration:
                return

        content = xml_file.read_text(encoding="utf-8")
        modified = False

        for name, value in features.items():
            str_value = str(value).lower()
            pattern = re.compile(rf'<bool name="{re.escape(name)}">.*?</bool>')

            if pattern.search(content):
                new_tag = f'<bool name="{name}">{str_value}</bool>'
                new_content = pattern.sub(new_tag, content)
                if new_content != content:
                    content = new_content
                    modified = True
            else:
                if "</features>" in content:
                    new_tag = f'    <bool name="{name}">{str_value}</bool>\n</features>'
                    content = content.replace("</features>", new_tag)
                    modified = True

        if modified:
            xml_file.write_text(content, encoding="utf-8")

    def _apply_build_props(self, props_map: Dict[str, Dict], wild_boost_enabled: bool):
        """Apply build property modifications."""
        # Filter wild_boost specific props if not enabled
        if not wild_boost_enabled and "product" in props_map:
            product_props = props_map["product"]
            filtered_props = {
                k: v
                for k, v in product_props.items()
                if not k.startswith("ro.product.spoofed")
                and not k.startswith("ro.spoofed")
                and not (
                    k.startswith("persist.prophook.com.xiaomi.joyose")
                    or k.startswith("persist.prophook.com.miui.powerkeeper")
                )
            }
            if filtered_props:
                props_map["product"] = filtered_props
            else:
                del props_map["product"]

        # Apply to partitions
        for partition, props in props_map.items():
            prop_file = self.ctx.get_target_prop_file(partition)

            if not prop_file or not prop_file.exists():
                self.logger.debug(f"build.prop not found for partition: {partition}")
                continue

            self.logger.info(
                f"Applying build_props to {partition} ({prop_file.relative_to(self.ctx.target_dir)})"
            )

            content = prop_file.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()

            # Map existing keys to their line index
            prop_indices = {}
            for i, line in enumerate(lines):
                if "=" in line and not line.strip().startswith("#"):
                    key = line.split("=")[0].strip()
                    prop_indices[key] = i

            modified = False
            new_lines = list(lines)

            for key, value in props.items():
                new_entry = f"{key}={value}"
                if key in prop_indices:
                    idx = prop_indices[key]
                    if new_lines[idx] != new_entry:
                        self.logger.debug(f"  Updating: {new_lines[idx]} -> {new_entry}")
                        new_lines[idx] = new_entry
                        modified = True
                else:
                    self.logger.debug(f"  Adding: {new_entry}")
                    new_lines.append(new_entry)
                    modified = True

            if modified:
                prop_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    def _apply_eu_localization_props(self):
        """Apply EU localization properties."""
        self.logger.info("Enabling EU Localization properties...")
        eu_cfg_path = Path("devices/common/eu_localization.json")

        if eu_cfg_path.exists():
            try:
                with open(eu_cfg_path, "r") as f:
                    eu_config = json.load(f)
                eu_props = eu_config.get("build_props", {})
                self._apply_build_props(eu_props, True)
            except Exception as e:
                self.logger.error(f"Failed to apply EU localization props: {e}")
