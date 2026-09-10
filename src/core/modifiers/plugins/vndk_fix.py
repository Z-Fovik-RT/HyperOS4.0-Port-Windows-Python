"""VNDK fix plugin.

This plugin fixes VNDK APEX and VINTF manifest issues.
"""

import re
import shutil
from pathlib import Path
from typing import Optional

from src.core.modifiers.plugin_system import ModifierPlugin, ModifierRegistry


@ModifierRegistry.register
class VNDKFixPlugin(ModifierPlugin):
    """Plugin to fix VNDK APEX and VINTF manifest."""

    name = "vndk_fix"
    description = "Fix VNDK APEX and VINTF manifest"
    priority = 40

    def modify(self) -> bool:
        """Apply VNDK fixes."""
        self._fix_vndk_apex()
        self._fix_vintf_manifest()
        return True

    def _fix_vndk_apex(self):
        """Copy missing VNDK APEX from stock."""
        vndk_version = self.ctx.stock.get_prop("ro.vndk.version")

        if not vndk_version:
            for prop in (self.ctx.stock.extracted_dir / "vendor").rglob("*.prop"):
                try:
                    with open(prop, errors="ignore") as f:
                        for line in f:
                            if "ro.vndk.version=" in line:
                                vndk_version = line.split("=")[1].strip()
                                break
                except:
                    pass
                if vndk_version:
                    break

        if not vndk_version:
            return

        apex_name = f"com.android.vndk.v{vndk_version}.apex"
        stock_apex = self._find_file_recursive(
            self.ctx.stock.extracted_dir / "system_ext/apex", apex_name
        )
        target_apex_dir = self.ctx.target_dir / "system_ext/apex"

        if stock_apex and target_apex_dir.exists():
            target_file = target_apex_dir / apex_name
            if not target_file.exists():
                self.logger.info(f"Copying missing VNDK Apex: {apex_name}")
                shutil.copy2(stock_apex, target_file)

    def _fix_vintf_manifest(self):
        """Fix VINTF manifest for VNDK version."""
        self.logger.info("Checking VINTF manifest for VNDK version...")

        vndk_version = self.ctx.stock.get_prop("ro.vndk.version")
        if not vndk_version:
            vendor_prop = self.ctx.target_dir / "vendor/build.prop"
            if vendor_prop.exists():
                try:
                    content = vendor_prop.read_text(encoding="utf-8", errors="ignore")
                    match = re.search(r"ro\.vndk\.version=(.*)", content)
                    if match:
                        vndk_version = match.group(1).strip()
                except:
                    pass

        if not vndk_version:
            self.logger.warning("Could not determine VNDK version")
            return

        target_xml = self._find_file_recursive(self.ctx.target_dir / "system_ext", "manifest.xml")
        if not target_xml:
            return

        original_content = target_xml.read_text(encoding="utf-8")

        if f"<version>{vndk_version}</version>" in original_content:
            return

        new_block = f"""    <vendor-ndk>
        <version>{vndk_version}</version>
    </vendor-ndk>"""

        if "</manifest>" in original_content:
            new_content = original_content.replace("</manifest>", f"{new_block}\n</manifest>")
            target_xml.write_text(new_content, encoding="utf-8")
            self.logger.info(f"Injected VNDK {vndk_version} into manifest")

    def _find_file_recursive(self, root_dir: Path, filename: str) -> Optional[Path]:
        if not root_dir.exists():
            return None
        try:
            return next(root_dir.rglob(filename))
        except StopIteration:
            return None
