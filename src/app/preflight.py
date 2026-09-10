"""Preflight checks for ROM porting inputs and runtime readiness."""

from __future__ import annotations

import json
import logging
import shutil
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.core.rom.constants import RomType
from src.core.rom.package import RomPackage
from src.core.tooling import resolve_tooling


@dataclass
class PreflightFinding:
    """A single preflight finding item."""

    severity: str
    code: str
    message: str
    target: str
    action: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class PreflightReport:
    """Structured preflight report with findings and metadata."""

    metadata: dict[str, Any] = field(default_factory=dict)
    findings: list[PreflightFinding] = field(default_factory=list)

    def add(
        self,
        *,
        severity: str,
        code: str,
        message: str,
        target: str,
        action: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        self.findings.append(
            PreflightFinding(
                severity=severity,
                code=code,
                message=message,
                target=target,
                action=action,
                details=details or {},
            )
        )

    @property
    def blockers(self) -> list[PreflightFinding]:
        return [finding for finding in self.findings if finding.severity == "blocker"]

    @property
    def risks(self) -> list[PreflightFinding]:
        return [finding for finding in self.findings if finding.severity == "risk"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata,
            "summary": {
                "total_findings": len(self.findings),
                "blockers": len(self.blockers),
                "risks": len(self.risks),
            },
            "findings": [asdict(finding) for finding in self.findings],
        }

    def has_blockers(self) -> bool:
        return bool(self.blockers)

    def has_failures(self, strict: bool = False) -> bool:
        """Return whether report contains blocking findings for requested strictness."""
        return bool(self.blockers or (strict and self.risks))


def _inspect_zip(path: Path) -> dict[str, bool]:
    """Inspect ZIP contents to detect packaging markers."""
    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
    return {
        "has_payload": "payload.bin" in names,
        "has_super": ("super.img" in names or "images/super.img" in names),
        "has_sparse_super_chunks": any(name.startswith("images/super.img.") for name in names),
        "has_brotli_images": any(name.endswith("new.dat.br") for name in names),
    }


def _check_input_path(report: PreflightReport, *, path: str | None, label: str) -> Path | None:
    """Validate the local path for a required input artifact."""
    if not path:
        report.add(
            severity="blocker",
            code=f"{label.upper()}_MISSING",
            message=f"{label.capitalize()} input is missing.",
            target=label,
            action=f"Provide a valid --{label} path.",
        )
        return None

    resolved = Path(path).resolve()
    if not resolved.exists():
        report.add(
            severity="blocker",
            code=f"{label.upper()}_NOT_FOUND",
            message=f"{label.capitalize()} path does not exist: {resolved}",
            target=label,
            action=f"Fix --{label} to point to an existing ROM artifact.",
            details={"path": str(resolved)},
        )
        return None

    return resolved


def _check_eu_bundle(report: PreflightReport, eu_bundle: str | None) -> None:
    """Validate optional EU bundle input."""
    if not eu_bundle:
        return

    bundle_path = Path(eu_bundle).resolve()
    if not bundle_path.exists():
        report.add(
            severity="blocker",
            code="EU_BUNDLE_NOT_FOUND",
            message=f"EU bundle does not exist: {bundle_path}",
            target="eu_bundle",
            action="Fix --eu-bundle path or remove the flag.",
            details={"path": str(bundle_path)},
        )
        return

    if not zipfile.is_zipfile(bundle_path):
        report.add(
            severity="blocker",
            code="EU_BUNDLE_INVALID_ZIP",
            message=f"EU bundle is not a valid ZIP archive: {bundle_path}",
            target="eu_bundle",
            action="Provide a valid EU bundle ZIP file.",
            details={"path": str(bundle_path)},
        )
        return

    with zipfile.ZipFile(bundle_path, "r") as archive:
        apk_count = sum(1 for name in archive.namelist() if name.lower().endswith(".apk"))
    if apk_count == 0:
        report.add(
            severity="risk",
            code="EU_BUNDLE_NO_APK",
            message="EU bundle ZIP contains no APK files.",
            target="eu_bundle",
            action="Verify bundle packaging and include required APK payloads.",
            details={"path": str(bundle_path)},
        )


def run_preflight(args, is_official_modify: bool, logger: logging.Logger) -> PreflightReport:
    """Run preflight checks and return a structured report."""
    report = PreflightReport(
        metadata={
            "stock": args.stock,
            "port": args.port,
            "is_official_modify": is_official_modify,
            "work_dir": args.work_dir,
            "phases": args.phases or [],
        }
    )

    stock_path = _check_input_path(report, path=args.stock, label="stock")
    port_path = (
        stock_path
        if is_official_modify
        else _check_input_path(report, path=args.port, label="port")
    )

    _check_eu_bundle(report, args.eu_bundle)

    work_dir = Path(args.work_dir).resolve()
    try:
        work_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        report.add(
            severity="blocker",
            code="WORK_DIR_NOT_WRITABLE",
            message=f"Cannot create or write work directory: {work_dir}",
            target="work_dir",
            action="Use a writable --work-dir path and retry.",
            details={"error": str(exc)},
        )

    detected_types: dict[str, str] = {}
    for label, candidate in (("stock", stock_path), ("port", port_path)):
        if candidate is None:
            continue
        try:
            rom = RomPackage(candidate, work_dir / f".preflight-{label}", label=f"{label.upper()}-Preflight")
            detected_types[label] = rom.rom_type.name
            if rom.rom_type == RomType.UNKNOWN:
                report.add(
                    severity="risk",
                    code=f"{label.upper()}_ROM_TYPE_UNKNOWN",
                    message=f"Could not confidently detect ROM type for {label}.",
                    target=label,
                    action="Check ROM artifact format (ZIP/payload/super images).",
                    details={"path": str(candidate)},
                )
            elif candidate.is_file() and zipfile.is_zipfile(candidate):
                markers = _inspect_zip(candidate)
                report.add(
                    severity="info",
                    code=f"{label.upper()}_ZIP_MARKERS",
                    message=f"{label.capitalize()} ZIP markers detected.",
                    target=label,
                    action="No action required.",
                    details=markers,
                )
        except Exception as exc:  # pragma: no cover - defensive
            report.add(
                severity="blocker",
                code=f"{label.upper()}_ROM_INIT_FAILED",
                message=f"Failed to initialize ROM package for {label}.",
                target=label,
                action="Check archive integrity and supported ROM structure.",
                details={"error": str(exc)},
            )

    # Host tool readiness checks based on detected input formats
    required_tools: set[str] = set()
    if "PAYLOAD" in detected_types.values():
        required_tools.add("payload-dumper")
    if "BROTLI" in detected_types.values():
        required_tools.add("brotli")
    if "LOCAL_DIR" in detected_types.values():
        # Local fastboot trees contain EROFS images that need a native extractor.
        required_tools.add("extract.erofs")

    resolved_tools = resolve_tooling(Path(__file__).resolve().parents[2], logger).tools
    for tool in sorted(required_tools):
        attr = tool.replace("-", "_").replace(".", "_")
        bundled = getattr(resolved_tools, attr, None)
        available = bool(bundled and bundled.exists()) or shutil.which(tool) is not None
        if not available:
            report.add(
                severity="blocker" if tool == "extract.erofs" else "risk",
                code="HOST_TOOL_MISSING",
                message=f"Required host tool is not available in PATH: {tool}",
                target="host",
                action=f"Run tools/setup_windows.ps1 for a native bundle or provide '{tool}' in PATH.",
                details={"tool": tool, "detected_rom_types": detected_types},
            )

    if stock_path and port_path and stock_path == port_path and not is_official_modify:
        report.add(
            severity="risk",
            code="STOCK_PORT_SAME_INPUT",
            message="Stock and Port inputs resolve to the same artifact.",
            target="inputs",
            action="Use different artifacts for --stock and --port unless in official mode.",
            details={"path": str(stock_path)},
        )

    if {"stock", "port"} <= detected_types.keys() and detected_types["stock"] != detected_types["port"]:
        report.add(
            severity="risk",
            code="ROM_TYPE_MISMATCH",
            message="Stock and Port ROM types differ; verify extraction strategy compatibility.",
            target="inputs",
            action="Confirm cross-type porting intent and compatible extraction strategy.",
            details=detected_types,
        )

    logger.info(
        "Preflight summary: blockers=%s, risks=%s, findings=%s",
        len(report.blockers),
        len(report.risks),
        len(report.findings),
    )
    for finding in report.findings:
        if finding.severity == "blocker":
            logger.error("[Preflight][%s] %s", finding.code, finding.message)
        elif finding.severity == "risk":
            logger.warning("[Preflight][%s] %s", finding.code, finding.message)
        else:
            logger.info("[Preflight][%s] %s", finding.code, finding.message)

    return report


def save_preflight_report(report: PreflightReport, output_path: str | Path) -> Path:
    """Persist preflight report as JSON."""
    path = Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return path
