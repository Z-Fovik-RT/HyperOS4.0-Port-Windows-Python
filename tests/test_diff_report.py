import logging
from pathlib import Path

import src.app.diff_report as diff_report
from src.app.diff_report import collect_artifact_state, generate_diff_report


def test_generate_diff_report_tracks_file_and_prop_changes(tmp_path: Path):
    target = tmp_path / "target"
    target.mkdir(parents=True)

    build_prop = target / "system" / "build.prop"
    build_prop.parent.mkdir(parents=True)
    build_prop.write_text("ro.product.name=device_a\nro.debuggable=0\n", encoding="utf-8")

    before = collect_artifact_state(target, logger=logging.getLogger("test"))

    build_prop.write_text("ro.product.name=device_b\nro.debuggable=0\n", encoding="utf-8")
    added = target / "system" / "new.conf"
    added.write_text("x", encoding="utf-8")

    after = collect_artifact_state(target, logger=logging.getLogger("test"))
    report = generate_diff_report(before, after)

    assert "system/new.conf" in report["files"]["added"]
    assert any(
        item["path"] == "system/build.prop"
        and item["key"] == "ro.product.name"
        and item["before"] == "device_a"
        and item["after"] == "device_b"
        for item in report["build_props"]["changes"]
    )
    assert "system/new.conf" in report["partition_groups"]["added"]["system"]
    assert "system/build.prop" in report["highlights"]["critical_path_changes"]
    assert any(
        flag["code"] == "IDENTITY_PROP_CHANGED"
        for flag in report["highlights"]["risk_flags"]
    )


def test_collect_artifact_state_hashes_each_file_once(tmp_path: Path, monkeypatch):
    target = tmp_path / "target"
    (target / "system").mkdir(parents=True)
    (target / "system" / "build.prop").write_text("ro.product.name=device_a\n", encoding="utf-8")
    (target / "system" / "app.apk").write_bytes(b"apk-bytes")
    (target / "system" / "plain.txt").write_text("hello", encoding="utf-8")

    hash_calls: list[str] = []
    original_sha = diff_report._sha256

    def counting_sha256(path: Path) -> str:
        hash_calls.append(str(path.relative_to(target)))
        return original_sha(path)

    monkeypatch.setattr(diff_report, "_sha256", counting_sha256)
    state = collect_artifact_state(target, logger=logging.getLogger("test"))

    assert sorted(hash_calls) == ["system/app.apk", "system/build.prop", "system/plain.txt"]
    assert "system/app.apk" in state["apks"]
