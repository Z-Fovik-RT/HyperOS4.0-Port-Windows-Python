"""Settings modification plugin.

EU/CN specific patches for Settings.apk.
"""
from pathlib import Path

from src.core.modifiers.plugins.apk.base import ApkModifierPlugin, ApkModifierRegistry


@ApkModifierRegistry.register
class SettingsModifier(ApkModifierPlugin):
    """Modify Settings.apk for EU/CN specific features."""
    
    name = "settings_modifier"
    description = "Apply EU/CN specific patches to Settings"
    apk_name = "Settings"
    package_name = "com.android.settings"
    priority = 100
    parallel_safe = True
    
    def _apply_patches(self, work_dir: Path):
        """Apply Settings patches based on ROM type."""
        self.logger.info("Processing Settings.apk...")
        
        is_eu = getattr(self.ctx, "is_port_eu_rom", False)
        
        if is_eu:
            self._apply_eu_patches(work_dir)
        else:
            self._apply_cn_patches(work_dir)
    
    def _apply_eu_patches(self, work_dir: Path):
        """Apply EU specific patches."""
        self.logger.info("Applying EU specific patches...")
        
        # Unlock Google Button
        self.smali_patch(
            work_dir,
            iname="MiuiSettings.smali",
            method="updateHeaderList",
            regex_replace=(r"sget-boolean\s+(v\d+|p\d+),.*IS_GLOBAL_BUILD:Z", r"const/4 \1, 0x1")
        )
    
    def _apply_cn_patches(self, work_dir: Path):
        """Apply CN specific patches."""
        self.logger.info("Applying CN specific patches...")
        
        # 1. Expand local register capacity
        self.smali_patch(
            work_dir,
            iname="IconDisplayCustomizationSettings.smali",
            method="setupShowNotificationIconCount",
            regex_replace=(r"\.locals\s+\d+", r".locals 7")
        )
        
        # 2. Replace array instructions
        regex = r'filled-new-array\s*\{([vp]\d+),\s*([vp]\d+),\s*([vp]\d+)\},\s*\[I'
        repl = (
            r'const/4 \1, 0x0\n'
            r'    const/4 \2, 0x1\n'
            r'    const/4 \3, 0x3\n'
            r'    const/4 v5, 0x5\n'
            r'    const/4 v6, 0x7\n'
            r'    filled-new-array {\1, \2, \3, v5, v6}, [I'
        )
        
        self.smali_patch(
            work_dir,
            iname="IconDisplayCustomizationSettings.smali",
            method="setupShowNotificationIconCount",
            regex_replace=(regex, repl)
        )
        
        # 3. XML patches for notification icons
        self._apply_notification_icon_xml(work_dir)
    
    def _apply_notification_icon_xml(self, work_dir: Path):
        """Apply XML patches for notification icon counts (5 and 7)."""
        self.logger.info("Applying notification icon XML patches...")
        
        res_dir = self.xml.get_res_dir(work_dir)
        
        # Add Multi-language Strings
        # English
        self.xml.add_string(res_dir, "display_notification_icon_5", "%d icons")
        self.xml.add_string(res_dir, "display_notification_icon_7", "%d icons")
        
        # Chinese
        self.xml.add_string(res_dir, "display_notification_icon_5", "显示%d个", "zh-rCN")
        self.xml.add_string(res_dir, "display_notification_icon_7", "显示%d个", "zh-rCN")
        
        # Add to entries array
        entries_to_add = [
            "@string/display_notification_icon_5",
            "@string/display_notification_icon_7"
        ]
        self.xml.add_array_item(
            res_dir,
            array_name="notification_icon_counts_entries",
            items=entries_to_add
        )
        
        # Add to values array
        values_to_add = ["5", "7"]
        self.xml.add_array_item(
            res_dir,
            array_name="notification_icon_counts_values",
            items=values_to_add
        )
        
        self.logger.info("Notification icon XML patches applied")
