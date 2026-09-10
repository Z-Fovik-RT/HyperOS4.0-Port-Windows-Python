import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.device_auto_config import get_or_create_device_config
from src.utils.payload_dumper import PayloadDumperOutput


def test_get_or_create_device_config_generates_partition_info_when_missing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    device_code = "fuxi"
    config_dir = tmp_path / "devices" / device_code
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_text("{}", encoding="utf-8")

    logger = MagicMock()
    payload_info = PayloadDumperOutput()

    with patch("src.core.device_auto_config.ConfigMerger") as merger_cls:
        merger = merger_cls.return_value
        merger.load_device_config.return_value = {"ok": True}

        config = get_or_create_device_config(
            device_code=device_code,
            payload_info=payload_info,
            stock_props={},
            logger=logger,
        )

    assert config == {"ok": True}
    info_path = config_dir / "partition_info.json"
    assert info_path.exists()

    payload = json.loads(info_path.read_text(encoding="utf-8"))
    assert payload["device_code"] == device_code
    assert "super_size" in payload
