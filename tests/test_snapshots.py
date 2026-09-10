import logging
from pathlib import Path

from src.app.snapshots import StageSnapshotManager


def test_snapshot_capture_and_restore(tmp_path: Path):
    source = tmp_path / "target"
    source.mkdir(parents=True)
    (source / "marker.txt").write_text("v1", encoding="utf-8")

    manager = StageSnapshotManager(tmp_path / "snapshots", logging.getLogger("test"))
    manager.capture("phase2_initialized", source)

    (source / "marker.txt").write_text("v2", encoding="utf-8")
    manager.restore("phase2_initialized", source)

    assert (source / "marker.txt").read_text(encoding="utf-8") == "v1"


def test_snapshot_list_names(tmp_path: Path):
    source = tmp_path / "target"
    source.mkdir(parents=True)
    (source / "a.txt").write_text("ok", encoding="utf-8")

    manager = StageSnapshotManager(tmp_path / "snapshots", logging.getLogger("test"))
    manager.capture("phase2_initialized", source)
    manager.capture("phase3_modified", source)

    assert manager.list_snapshot_names() == ["phase2_initialized", "phase3_modified"]
