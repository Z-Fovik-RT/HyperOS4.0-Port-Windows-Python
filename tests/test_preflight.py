import logging
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from src.app.preflight import run_preflight


def _make_args(tmp_path: Path, **overrides) -> Namespace:
    stock = tmp_path / "stock.zip"
    stock.write_bytes(b"not-a-zip")

    base = {
        "stock": str(stock),
        "port": str(stock),
        "work_dir": str(tmp_path / "work"),
        "eu_bundle": None,
        "phases": None,
        "preflight_report": str(tmp_path / "report.json"),
    }
    base.update(overrides)
    return Namespace(**base)


def test_run_preflight_reports_missing_port_when_not_official(tmp_path: Path):
    args = _make_args(tmp_path, port=str(tmp_path / "missing.zip"))

    report = run_preflight(args, is_official_modify=False, logger=logging.getLogger("test"))

    assert report.has_blockers()
    assert any(f.code == "PORT_NOT_FOUND" for f in report.findings)


def test_run_preflight_reports_invalid_eu_bundle(tmp_path: Path):
    bad_bundle = tmp_path / "bundle.zip"
    bad_bundle.write_text("bad zip", encoding="utf-8")
    args = _make_args(tmp_path, eu_bundle=str(bad_bundle))

    report = run_preflight(args, is_official_modify=True, logger=logging.getLogger("test"))

    assert any(f.code == "EU_BUNDLE_INVALID_ZIP" for f in report.findings)


def test_preflight_report_strict_mode_and_action_fields(tmp_path: Path):
    args = _make_args(tmp_path, port=str(tmp_path / "missing.zip"))
    report = run_preflight(args, is_official_modify=False, logger=logging.getLogger("test"))

    assert report.has_failures(strict=False) is True
    assert report.has_failures(strict=True) is True
    assert any(f.action for f in report.findings)


def test_run_preflight_reports_missing_required_host_tools(tmp_path: Path):
    args = _make_args(tmp_path)

    with patch("src.app.preflight.shutil.which", return_value=None), patch(
        "src.app.preflight.RomPackage"
    ) as rom_pkg_cls:
        rom_pkg_cls.return_value.rom_type.name = "PAYLOAD"
        report = run_preflight(args, is_official_modify=True, logger=logging.getLogger("test"))

    assert any(
        f.code == "HOST_TOOL_MISSING" and f.details.get("tool") == "payload-dumper"
        for f in report.findings
    )
