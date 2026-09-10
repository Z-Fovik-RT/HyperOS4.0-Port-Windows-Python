"""File replacement plugin.

This plugin handles file/directory replacements from configuration.
"""

import shutil
import zipfile
from pathlib import Path
from typing import Dict

from src.core.modifiers.plugin_system import ModifierPlugin, ModifierRegistry
from src.utils.download import AssetDownloader


@ModifierRegistry.register
class FileReplacementPlugin(ModifierPlugin):
    """Plugin to handle file/directory replacements from config."""

    name = "file_replacement"
    description = "Execute file/directory replacements from replacements.json"
    priority = 20

    def __init__(self, context, **kwargs):
        super().__init__(context, **kwargs)
        from src.core.conditions import ConditionEvaluator
        from src.core.config_merger import ConfigMerger
        from src.utils.shell import ShellRunner

        self.merger = ConfigMerger(self.logger)
        self.evaluator = ConditionEvaluator()
        self.downloader = AssetDownloader()
        self.shell = ShellRunner()

    def modify(self) -> bool:
        """Execute file replacements."""
        from src.core.conditions import BuildContext

        config = self._load_merged_config("replacements.json")
        replacements = config.get("replacements", [])

        if not replacements:
            return True

        self.logger.info(f"Processing {len(replacements)} file replacements...")

        # Build context for condition evaluation
        build_ctx = BuildContext()
        build_ctx.port_android_version = int(self.ctx.port_android_version)
        build_ctx.base_android_version = int(self.ctx.base_android_version)
        build_ctx.base_device_code = self.ctx.stock_rom_code
        build_ctx.port_os_version_incremental = (
            self.ctx.port.get_prop("ro.mi.os.version.incremental") or ""
        )
        build_ctx.is_port_eu_rom = getattr(self.ctx, "is_port_eu_rom", False)

        stock_root = self.ctx.stock.extracted_dir
        target_root = self.ctx.target_dir

        for rule in replacements:
            # Evaluate conditions
            passed, reason = self.evaluator.evaluate_with_reason(rule, build_ctx)
            if not passed:
                self.logger.debug(f"Rule '{rule.get('description', 'unnamed')}' skipped: {reason}")
                continue

            desc = rule.get("description", "Unknown Rule")
            rtype = rule.get("type", "file")
            self.logger.info(f"Applying replacement rule: {desc}")

            try:
                self._handle_rule(rule, rtype, stock_root, target_root)
            except Exception as e:
                self.logger.error(f"Failed to apply rule '{desc}': {e}")

        return True

    def _load_merged_config(self, filename: str) -> dict:
        """Load and merge configuration from common, chipset and target layers."""
        paths = [
            Path("devices/common"),
            Path(f"devices/{getattr(self.ctx, 'base_chipset_family', 'unknown')}"),
            Path(f"devices/{self.ctx.stock_rom_code}"),
        ]
        valid_paths = [p for p in paths if p.exists() and p.is_dir()]
        config, report = self.merger.load_and_merge(valid_paths, filename)

        if report.loaded_files:
            self.logger.info(f"Merged {filename} from: {', '.join(report.loaded_files)}")
        return config

    def _handle_rule(self, rule: Dict, rtype: str, stock_root: Path, target_root: Path):
        """Handle a single replacement rule based on type."""
        if rtype == "unzip_override":
            self._handle_unzip_override(rule, target_root)
        elif rtype == "wild_boost":
            # Wild boost is handled by its own plugin
            pass
        elif rtype == "copy_file_internal":
            self._handle_copy_file_internal(rule, target_root)
        elif rtype == "remove_files":
            self._handle_remove_files(rule, target_root)
        elif rtype == "hexpatch":
            self._handle_hexpatch(rule, target_root)
        elif rtype == "append_text":
            self._handle_append_text(rule, target_root)
        elif rtype == "copy_local":
            self._handle_copy_local(rule, target_root)
        else:
            self._handle_legacy_replacement(rule, stock_root, target_root)

    def _handle_unzip_override(self, rule: Dict, target_root: Path):
        """Handle unzip_override rule type."""
        source_zip = Path(rule["source"])
        if not source_zip.exists():
            self.logger.warning(f"Source zip not found: {source_zip}")
            return

        target_dir = target_root
        if "target" in rule:
            target_dir = target_dir / rule["target"]

        with zipfile.ZipFile(source_zip, "r") as z:
            z.extractall(target_dir)

    def _handle_copy_file_internal(self, rule: Dict, target_root: Path):
        """Handle copy_file_internal rule type."""
        source = target_root / rule["source"]
        target = target_root / rule["target"]

        if not source.exists():
            if rule.get("ensure_exists", False):
                self.logger.warning(f"Internal source not found: {rule['source']}")
            return

        target.parent.mkdir(parents=True, exist_ok=True)

        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            shutil.copy2(source, target)

    def _handle_remove_files(self, rule: Dict, target_root: Path):
        """Handle remove_files rule type."""
        files = rule.get("files", [])
        search_path = rule.get("search_path", "")

        for pattern in files:
            root = target_root / search_path
            for item in root.glob(pattern):
                self.logger.info(f"Removing: {item.relative_to(target_root)}")
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

    def _handle_hexpatch(self, rule: Dict, target_root: Path):
        """Handle hexpatch rule type."""
        target_val = rule["target"]
        target_files = []

        if "/" in target_val:
            tf = target_root / target_val
            if tf.exists():
                target_files.append(tf)
        else:
            target_files = list(target_root.rglob(target_val))

        if not target_files:
            self.logger.warning(f"HexPatch target not found: {target_val}")
            return

        for target_file in target_files:
            content = target_file.read_bytes()
            modified = False

            for patch in rule.get("patches", []):
                old_bytes = bytes.fromhex(patch["old"])
                new_bytes = bytes.fromhex(patch["new"])

                if old_bytes in content:
                    content = content.replace(old_bytes, new_bytes)
                    modified = True

            if modified:
                target_file.write_bytes(content)

    def _handle_append_text(self, rule: Dict, target_root: Path):
        """Handle append_text rule type."""
        target_file = target_root / rule["target"]
        if not target_file.exists():
            return

        text = rule.get("text", "")
        if not text:
            return

        content = target_file.read_text(encoding="utf-8", errors="ignore")
        if text not in content:
            with open(target_file, "a", encoding="utf-8") as f:
                f.write(f"\n{text}\n")

    def _handle_copy_local(self, rule: Dict, target_root: Path):
        """Handle copy_local rule type."""
        source = Path(rule["source"])
        if not source.exists():
            if not self.downloader.download_if_missing(source):
                return

        target_val = rule["target"]
        target_files = []

        if "/" in target_val:
            target_files.append(target_root / target_val)
        else:
            target_files = list(target_root.rglob(target_val))

        if not target_files:
            return

        for target_file in target_files:
            target_file.parent.mkdir(parents=True, exist_ok=True)

            if source.is_dir():
                shutil.copytree(source, target_file, dirs_exist_ok=True)
            else:
                shutil.copy2(source, target_file)

    def _handle_legacy_replacement(self, rule: Dict, stock_root: Path, target_root: Path):
        """Handle legacy file replacement rule type."""
        search_path = rule.get("search_path", "")
        match_mode = rule.get("match_mode", "exact")
        ensure_exists = rule.get("ensure_exists", False)
        files = rule.get("files", [])

        rule_stock_root = stock_root / search_path
        rule_target_root = target_root / search_path

        if not rule_stock_root.exists():
            return

        for pattern in files:
            sources = []
            if match_mode == "glob":
                sources = list(rule_stock_root.glob(pattern))
            elif match_mode == "recursive":
                sources = list(rule_stock_root.rglob(pattern))
            else:
                exact_file = rule_stock_root / pattern
                if exact_file.exists():
                    sources = [exact_file]

            for src_item in sources:
                rel_name = src_item.name
                target_item = rule_target_root / rel_name

                found_in_target = False
                if match_mode == "recursive":
                    candidates = list(rule_target_root.rglob(rel_name))
                    if candidates:
                        target_item = candidates[0]
                        found_in_target = True
                else:
                    if target_item.exists():
                        found_in_target = True

                should_copy = found_in_target or ensure_exists
                if should_copy:
                    target_item.parent.mkdir(parents=True, exist_ok=True)

                    if target_item.exists():
                        if target_item.is_dir():
                            shutil.rmtree(target_item)
                        else:
                            target_item.unlink()

                    if src_item.is_dir():
                        shutil.copytree(src_item, target_item, symlinks=True, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src_item, target_item)
