"""Stage snapshot and rollback helpers for workflow checkpoints."""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast


@dataclass
class SnapshotRecord:
    """Metadata for a captured stage snapshot."""

    name: str
    created_at: str
    source: str
    snapshot_path: str


class StageSnapshotManager:
    """Capture and restore workflow stage snapshots."""

    def __init__(self, root_dir: str | Path, logger: logging.Logger) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.logger = logger
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root_dir / "index.json"

    def _load_index(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return {"snapshots": []}
        try:
            loaded = json.loads(self.index_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                return cast(dict[str, Any], loaded)
            self.logger.warning("Snapshot index root is not an object. Reinitializing index.")
            return {"snapshots": []}
        except json.JSONDecodeError:
            self.logger.warning("Snapshot index is invalid JSON. Reinitializing index.")
            return {"snapshots": []}

    def _save_index(self, data: dict[str, Any]) -> None:
        self.index_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def capture(self, name: str, source_dir: str | Path) -> Path:
        """Capture a snapshot for a workflow stage."""
        source = Path(source_dir).resolve()
        if not source.exists():
            raise FileNotFoundError(f"Snapshot source does not exist: {source}")

        snapshot_dir = self.root_dir / name
        if snapshot_dir.exists():
            shutil.rmtree(snapshot_dir)
        shutil.copytree(source, snapshot_dir, dirs_exist_ok=True)

        index = self._load_index()
        snapshots = [
            entry for entry in index.get("snapshots", []) if entry.get("name") != name
        ]
        snapshots.append(
            {
                "name": name,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "source": str(source),
                "snapshot_path": str(snapshot_dir),
            }
        )
        index["snapshots"] = snapshots
        self._save_index(index)
        self.logger.info(f"Snapshot captured: {name} -> {snapshot_dir}")
        return snapshot_dir

    def restore(self, name: str, target_dir: str | Path) -> Path:
        """Restore target directory from a named snapshot."""
        snapshot_dir = self.root_dir / name
        if not snapshot_dir.exists():
            raise FileNotFoundError(f"Snapshot not found: {name}")

        target = Path(target_dir).resolve()
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(snapshot_dir, target, dirs_exist_ok=True)
        self.logger.info(f"Snapshot restored: {name} -> {target}")
        return target

    def list_snapshot_names(self) -> list[str]:
        """Return available snapshot names from index."""
        index = self._load_index()
        return [entry["name"] for entry in index.get("snapshots", []) if "name" in entry]
