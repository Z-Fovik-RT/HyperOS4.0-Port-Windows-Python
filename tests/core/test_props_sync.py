import logging
from types import SimpleNamespace

# Ensure modifier package is initialized before importing PropertyModifier.
import src.core.modifiers  # noqa: F401
from src.core.props import PropertyModifier


def _build_context(tmp_path):
    stock_extracted = tmp_path / "stock" / "extracted"
    target_dir = tmp_path / "target"
    stock_prop = stock_extracted / "product" / "etc" / "build.prop"
    target_prop = target_dir / "product" / "etc" / "build.prop"
    stock_prop.parent.mkdir(parents=True, exist_ok=True)
    target_prop.parent.mkdir(parents=True, exist_ok=True)

    ctx = SimpleNamespace(
        stock=SimpleNamespace(extracted_dir=stock_extracted),
        target_dir=target_dir,
        stock_rom_code="pudding",
        base_chipset_family="unknown",
    )
    return ctx, stock_prop, target_prop


def test_sync_product_build_prop_updates_and_appends_missing_keys(tmp_path):
    ctx, stock_prop, target_prop = _build_context(tmp_path)
    stock_prop.write_text(
        "\n".join(
            [
                "ro.sync.key=stock_value",
                "ro.build.version.incremental=stock_inc",
                "ro.only.stock=stock_only",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    target_prop.write_text(
        "\n".join(
            [
                "ro.sync.key=target_value",
                "ro.build.version.incremental=target_inc",
                "ro.only.target=target_only",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    modifier = PropertyModifier(ctx, logger=logging.getLogger("test.props.sync"))
    modifier._sync_product_build_prop_from_stock()

    result = target_prop.read_text(encoding="utf-8")
    assert "ro.sync.key=stock_value" in result
    assert "ro.build.version.incremental=target_inc" in result
    assert "ro.only.target=target_only" in result
    assert "ro.only.stock=stock_only" in result


def test_sync_product_build_prop_skips_when_source_missing(tmp_path):
    ctx, _, target_prop = _build_context(tmp_path)
    target_prop.write_text("ro.sync.key=target_value\n", encoding="utf-8")

    modifier = PropertyModifier(ctx, logger=logging.getLogger("test.props.sync"))
    modifier._sync_product_build_prop_from_stock()

    assert target_prop.read_text(encoding="utf-8") == "ro.sync.key=target_value\n"


def test_sync_product_build_prop_uses_common_config_skip_keys(tmp_path, monkeypatch):
    ctx, stock_prop, target_prop = _build_context(tmp_path)
    stock_prop.write_text("ro.sync.key=stock_value\n", encoding="utf-8")
    target_prop.write_text("ro.sync.key=target_value\n", encoding="utf-8")

    devices_common = tmp_path / "devices" / "common"
    devices_common.mkdir(parents=True, exist_ok=True)
    (devices_common / "props_sync.json").write_text(
        '{\n  "product_build_prop_sync": {\n    "skip_keys": ["ro.sync.key"]\n  }\n}\n',
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    modifier = PropertyModifier(ctx, logger=logging.getLogger("test.props.sync"))
    modifier._sync_product_build_prop_from_stock()

    assert target_prop.read_text(encoding="utf-8") == "ro.sync.key=target_value\n"
