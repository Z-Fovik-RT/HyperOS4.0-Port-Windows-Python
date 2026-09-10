"""Artifact diff report generation for porting outputs."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

PARTITION_KEYS = {
    "system",
    "product",
    "system_ext",
    "vendor",
    "odm",
    "mi_ext",
    "vendor_dlkm",
    "vendor_boot",
    "boot",
}

CRITICAL_PATH_MARKERS = (
    "/etc/selinux/",
    "/sepolicy/",
    "build.prop",
    "file_contexts",
    "fs_config",
    "/etc/init/",
    "init.rc",
    "/framework/",
    "/priv-app/",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_prop_file(path: Path) -> dict[str, str]:
    props: dict[str, str] = {}
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            props[key.strip()] = value.strip()
    return props


@lru_cache(maxsize=1)
def _resolve_aapt_tool() -> str | None:
    for tool in ("aapt2", "aapt"):
        if shutil.which(tool):
            return tool
    return None


def _extract_apk_metadata(apk_path: Path, file_meta: dict[str, Any] | None = None) -> dict[str, Any]:
    if file_meta is None:
        file_meta = {"size": apk_path.stat().st_size, "sha256": _sha256(apk_path)}

    metadata: dict[str, Any] = {
        "size": file_meta["size"],
        "sha256": file_meta["sha256"],
        "package": None,
        "version_name": None,
        "version_code": None,
    }

    tool = _resolve_aapt_tool()
    if tool is None:
        return metadata

    proc = subprocess.run(
        [tool, "dump", "badging", str(apk_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        return metadata

    match = re.search(
        r"package: name='([^']+)'.*versionCode='([^']+)'.*versionName='([^']*)'",
        proc.stdout,
    )
    if match:
        metadata["package"] = match.group(1)
        metadata["version_code"] = match.group(2)
        metadata["version_name"] = match.group(3)
    return metadata


def _collect_state_entries(
    root: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, str]], dict[str, dict[str, Any]]]:
    files: dict[str, dict[str, Any]] = {}
    build_props: dict[str, dict[str, str]] = {}
    apks: dict[str, dict[str, Any]] = {}

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root))
        file_meta = {
            "size": path.stat().st_size,
            "sha256": _sha256(path),
        }
        files[rel] = file_meta

        if path.name == "build.prop":
            build_props[rel] = _parse_prop_file(path)
        if path.suffix == ".apk":
            apks[rel] = _extract_apk_metadata(path, file_meta=file_meta)

    return files, build_props, apks


def collect_artifact_state(root: str | Path, logger: logging.Logger) -> dict[str, Any]:
    """Collect file, build.prop, and APK metadata state for diffing."""
    target = Path(root).resolve()
    if not target.exists():
        logger.warning("Artifact state target does not exist: %s", target)
        return {"root": str(target), "files": {}, "build_props": {}, "apks": {}}

    logger.info("Collecting artifact state from: %s", target)
    files, build_props, apks = _collect_state_entries(target)
    return {
        "root": str(target),
        "files": files,
        "build_props": build_props,
        "apks": apks,
    }


def _diff_map(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[str]]:
    before_keys = set(before.keys())
    after_keys = set(after.keys())
    return {
        "added": sorted(after_keys - before_keys),
        "removed": sorted(before_keys - after_keys),
        "common": sorted(before_keys & after_keys),
    }


def _partition_for_path(path: str) -> str:
    first = path.split("/", 1)[0]
    if first in PARTITION_KEYS:
        return first
    return "_root"


def _group_paths_by_partition(paths: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for path in paths:
        partition = _partition_for_path(path)
        grouped.setdefault(partition, []).append(path)
    for partition, entries in grouped.items():
        grouped[partition] = sorted(entries)
    return dict(sorted(grouped.items(), key=lambda item: item[0]))


def _collect_critical_path_changes(
    file_changes: dict[str, list[str]], apk_changes: list[dict[str, Any]]
) -> list[str]:
    candidates = file_changes["added"] + file_changes["removed"] + file_changes["modified"]
    candidates.extend(change["path"] for change in apk_changes)
    critical = []
    for path in candidates:
        if any(marker in path for marker in CRITICAL_PATH_MARKERS):
            critical.append(path)
    return sorted(set(critical))


def _build_risk_flags(
    file_changes: dict[str, list[str]],
    prop_changes: list[dict[str, Any]],
    apk_changes: list[dict[str, Any]],
    critical_paths: list[str],
) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []

    if critical_paths:
        flags.append(
            {
                "code": "HIGH_IMPACT_PATH_CHANGED",
                "message": "Critical system/security paths changed.",
                "paths": critical_paths,
            }
        )

    identity_prop_paths = sorted(
        {
            item["path"]
            for item in prop_changes
            if item["key"].startswith("ro.product.")
            or item["key"].startswith("ro.build.fingerprint")
        }
    )
    if identity_prop_paths:
        flags.append(
            {
                "code": "IDENTITY_PROP_CHANGED",
                "message": "Device identity properties changed.",
                "paths": identity_prop_paths,
            }
        )

    priv_app_paths = sorted(
        {
            change["path"]
            for change in apk_changes
            if "/priv-app/" in change["path"] or change["path"].startswith("priv-app/")
        }
    )
    if priv_app_paths:
        flags.append(
            {
                "code": "PRIV_APP_CHANGED",
                "message": "Privileged APK content changed.",
                "paths": priv_app_paths,
            }
        )

    init_related = sorted(
        path
        for path in (file_changes["added"] + file_changes["removed"] + file_changes["modified"])
        if "/etc/init/" in path or path.endswith("init.rc")
    )
    if init_related:
        flags.append(
            {
                "code": "INIT_SCRIPT_CHANGED",
                "message": "Init scripts changed and may affect boot.",
                "paths": init_related,
            }
        )

    return flags


def generate_diff_report(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Generate a structured artifact diff report."""
    file_scope = _diff_map(before.get("files", {}), after.get("files", {}))
    modified_files = [
        path
        for path in file_scope["common"]
        if before["files"][path] != after["files"][path]
    ]

    prop_changes: list[dict[str, Any]] = []
    prop_scope = _diff_map(before.get("build_props", {}), after.get("build_props", {}))
    for prop_path in prop_scope["common"]:
        before_props = before["build_props"][prop_path]
        after_props = after["build_props"][prop_path]
        keys = set(before_props.keys()) | set(after_props.keys())
        for key in sorted(keys):
            if before_props.get(key) != after_props.get(key):
                prop_changes.append(
                    {
                        "path": prop_path,
                        "key": key,
                        "before": before_props.get(key),
                        "after": after_props.get(key),
                    }
                )

    apk_changes: list[dict[str, Any]] = []
    apk_scope = _diff_map(before.get("apks", {}), after.get("apks", {}))
    for path in apk_scope["added"]:
        apk_changes.append({"path": path, "change": "added", "before": None, "after": after["apks"][path]})
    for path in apk_scope["removed"]:
        apk_changes.append({"path": path, "change": "removed", "before": before["apks"][path], "after": None})
    for path in apk_scope["common"]:
        if before["apks"][path] != after["apks"][path]:
            apk_changes.append(
                {
                    "path": path,
                    "change": "modified",
                    "before": before["apks"][path],
                    "after": after["apks"][path],
                }
            )

    file_changes = {
        "added": file_scope["added"],
        "removed": file_scope["removed"],
        "modified": modified_files,
    }
    critical_paths = _collect_critical_path_changes(file_changes, apk_changes)
    risk_flags = _build_risk_flags(file_changes, prop_changes, apk_changes, critical_paths)

    return {
        "summary": {
            "files_added": len(file_scope["added"]),
            "files_removed": len(file_scope["removed"]),
            "files_modified": len(modified_files),
            "prop_changes": len(prop_changes),
            "apk_changes": len(apk_changes),
            "risk_flags": len(risk_flags),
        },
        "files": file_changes,
        "build_props": {
            "added_files": prop_scope["added"],
            "removed_files": prop_scope["removed"],
            "changes": prop_changes,
        },
        "apks": apk_changes,
        "partition_groups": {
            "added": _group_paths_by_partition(file_scope["added"]),
            "removed": _group_paths_by_partition(file_scope["removed"]),
            "modified": _group_paths_by_partition(modified_files),
        },
        "highlights": {
            "critical_path_changes": critical_paths,
            "risk_flags": risk_flags,
        },
    }


def save_diff_report(report: dict[str, Any], output_path: str | Path) -> Path:
    """Persist the generated diff report to JSON."""
    path = Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path
