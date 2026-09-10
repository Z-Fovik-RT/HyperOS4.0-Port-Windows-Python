from types import SimpleNamespace

from src.core.packer import build_rom_filename_device_tag, build_rom_filename_prefix


def test_build_rom_filename_prefix_for_eu() -> None:
    ctx = SimpleNamespace(
        is_port_eu_rom=True,
        is_port_global_rom=False,
        port_global_region="",
    )
    assert build_rom_filename_prefix(ctx) == "xiaomi.eu_"


def test_build_rom_filename_prefix_for_global_regions() -> None:
    for region in ("global", "eea", "ru", "in", "id", "tr", "lm_cr", "tw"):
        ctx = SimpleNamespace(
            is_port_eu_rom=False,
            is_port_global_rom=True,
            port_global_region=region,
        )
        assert build_rom_filename_prefix(ctx) == ""


def test_build_rom_filename_device_tag_for_global_variants() -> None:
    cases = (
        ("global", "fuxi_global"),
        ("eea", "fuxi_eea_global"),
        ("ru", "fuxi_ru_global"),
        ("in", "fuxi_in_global"),
        ("id", "fuxi_id_global"),
        ("tr", "fuxi_tr_global"),
        ("lm_cr", "fuxi_lm_cr_global"),
        ("tw", "fuxi_tw_global"),
    )
    for region, expected in cases:
        ctx = SimpleNamespace(
            stock_rom_code="fuxi",
            is_port_eu_rom=False,
            is_port_global_rom=True,
            port_global_region=region,
        )
        assert build_rom_filename_device_tag(ctx) == expected


def test_build_rom_filename_device_tag_for_unknown_global_fallback() -> None:
    ctx = SimpleNamespace(
        stock_rom_code="fuxi",
        is_port_eu_rom=False,
        is_port_global_rom=True,
        port_global_region="",
    )
    assert build_rom_filename_device_tag(ctx) == "fuxi_global"


def test_build_rom_filename_device_tag_for_non_global_non_eu() -> None:
    ctx = SimpleNamespace(
        stock_rom_code="fuxi",
        is_port_eu_rom=False,
        is_port_global_rom=False,
        port_global_region="",
    )
    assert build_rom_filename_device_tag(ctx) == "fuxi"
