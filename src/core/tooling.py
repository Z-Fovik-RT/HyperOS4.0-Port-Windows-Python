"""Tool resolution helpers for the porting workflow."""

from __future__ import annotations

import logging
import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace


@dataclass
class ResolvedTooling:
    """Resolved tool locations for the current host platform."""

    platform_bin_dir: Path
    tools: SimpleNamespace


def _tool_path(*candidates: Path | str, extensions: tuple[str, ...] = ("", ".exe")) -> Path:
    """Return the first existing candidate, or a PATH command fallback."""
    for candidate in candidates:
        path = Path(candidate)
        for suffix in extensions:
            # A dotted tool name such as ``mkfs.erofs`` is not a file suffix.
            probe = path if suffix == "" else (
                path if path.suffix.lower() == suffix else Path(str(path) + suffix)
            )
            if probe.exists():
                if os.name == "nt" and _is_elf(probe):
                    continue
                return probe
    for candidate in candidates:
        name = Path(candidate).name
        for suffix in extensions:
            found = shutil.which(name if suffix == "" else name + suffix)
            if found:
                found_path = Path(found)
                if os.name != "nt" or not _is_elf(found_path):
                    return found_path
    return Path(Path(candidates[0]).name if candidates else "")


def _is_elf(path: Path) -> bool:
    try:
        with path.open("rb") as stream:
            return stream.read(4) == b"\x7fELF"
    except OSError:
        return False


def resolve_tooling(project_root: Path, logger: logging.Logger) -> ResolvedTooling:
    """Resolve platform-specific binaries and shared tool locations."""
    bin_root = project_root / "bin"
    system = platform.system().lower()
    machine = platform.machine().lower()

    if machine in ["amd64", "x86_64"]:
        arch = "x86_64"
    elif machine in ["aarch64", "arm64"]:
        arch = "arm64"
    else:
        arch = "x86_64"

    if system == "windows":
        platform_dir = "windows"
        executable_extension = ".exe"
    elif system == "linux":
        platform_dir = "linux"
        executable_extension = ""
    elif system == "darwin":
        platform_dir = "macos"
        executable_extension = ""
    else:
        logger.warning(f"Unknown system: {system}, defaulting to Windows-compatible lookup.")
        platform_dir = "windows"
        executable_extension = ".exe" if os.name == "nt" else ""

    platform_bin_dir = bin_root / platform_dir / arch
    fallback_dir = bin_root / platform_dir
    if not platform_bin_dir.exists() and fallback_dir.exists():
        platform_bin_dir = fallback_dir

    logger.info(f"Platform Binary Dir: {platform_bin_dir}")

    # Some projects keep Android host tools under the flash bundle rather than
    # bin/windows. Include that directory in the lookup without copying files.
    windows_flash_dir = bin_root / "flash" / "platform-tools-windows"
    def resolve(name: str) -> Path:
        return _tool_path(
            platform_bin_dir / name,
            platform_bin_dir / f"{name}{executable_extension}",
            windows_flash_dir / name,
            windows_flash_dir / f"{name}{executable_extension}",
            name,
            extensions=("", ".exe") if system == "windows" else ("",),
        )

    tools = SimpleNamespace()
    tools.magiskboot = resolve("magiskboot")
    tools.aapt2 = resolve("aapt2")
    for name in ("payload_dumper", "payload-dumper", "brotli", "lpunpack",
                 "simg2img", "img2simg", "extract.erofs", "mkfs.erofs", "mke2fs",
                 "e2fsdroid", "lpmake", "avbtool", "zstd"):
        attr = name.replace("-", "_").replace(".", "_")
        setattr(tools, attr, resolve(name))
    tools.apktool_jar = bin_root / "apktool" / "apktool_2.12.1.jar"
    tools.apkeditor_jar = bin_root / "APKEditor.jar"

    if not tools.magiskboot.exists():
        logger.warning(f"magiskboot not found at {tools.magiskboot}")

    return ResolvedTooling(platform_bin_dir=platform_bin_dir, tools=tools)
