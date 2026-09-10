from pathlib import Path
from types import SimpleNamespace

from src.core.modifiers.firmware_modifier import FirmwareModifier


def _build_context(tmp_path: Path) -> SimpleNamespace:
    magiskboot = tmp_path / "magiskboot"
    magiskboot.write_bytes(b"stub")

    repack_images = tmp_path / "target" / "repack_images"
    repack_images.mkdir(parents=True, exist_ok=True)

    return SimpleNamespace(
        target_dir=tmp_path / "target",
        tools=SimpleNamespace(magiskboot=magiskboot),
        device_config={},
    )


def test_patch_vbmeta_sets_avb_flags_to_one(tmp_path: Path):
    ctx = _build_context(tmp_path)
    vbmeta_img = ctx.target_dir / "repack_images" / "vbmeta.img"

    payload = bytearray(256)
    payload[0:4] = b"AVB0"
    payload[123] = 0x00
    vbmeta_img.write_bytes(payload)

    modifier = FirmwareModifier(ctx)
    modifier._patch_vbmeta()

    patched = vbmeta_img.read_bytes()
    assert patched[123] == 0x01
