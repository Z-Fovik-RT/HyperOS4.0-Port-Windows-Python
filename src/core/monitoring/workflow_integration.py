"""Integration of monitoring into the main ROM porting workflow.

This module integrates monitoring with the existing system.
"""

from pathlib import Path
from typing import Optional

from src.core.context import PortingContext
from src.core.monitoring import get_monitor
from src.core.monitoring.console_ui import ConsoleReporter


class MonitoredPortingWorkflow:
    """ROM porting workflow with integrated monitoring.

    This wraps the standard porting process with comprehensive monitoring.
    """

    def __init__(self, context: PortingContext, report_path: Optional[Path] = None):
        self.ctx = context
        self.report_path = report_path or Path("porting_report.json")
        self.monitor = get_monitor()
        self.reporter = ConsoleReporter()

        # Setup progress listener
        self.monitor.add_progress_listener(self.reporter.on_progress_update)

    def run(self) -> bool:
        """Execute the full porting workflow with monitoring."""
        from src.core.modifiers import (
            ApkModifier,
            FirmwareModifier,
            FrameworkModifier,
            RomModifier,
            SystemModifier,
        )
        from src.core.packer import Repacker
        from src.core.props import PropertyModifier

        self.monitor.start()

        try:
            # Phase 1: System Modification
            with self.monitor.phase("system_modification"):
                self.reporter.on_phase_start("System Modification")
                system_modifier = SystemModifier(self.ctx)
                system_modifier.run()
                self.reporter.on_phase_end(
                    "System Modification",
                    True,
                    self.monitor.report.execution_tracer.get_summary()["total_duration"],
                )

            # Phase 2: Property Modification
            with self.monitor.phase("property_modification"):
                self.reporter.on_phase_start("Property Modification")
                PropertyModifier(self.ctx).run()
                self.reporter.on_phase_end(
                    "Property Modification",
                    True,
                    0,  # Duration tracked by tracer
                )

            # Phase 3: Framework Modification
            with self.monitor.phase("framework_modification"):
                self.reporter.on_phase_start("Framework Modification")
                fw_modifier = FrameworkModifier(self.ctx)
                fw_modifier.run()
                self.reporter.on_phase_end("Framework Modification", True, 0)

            # Phase 4: Firmware Modification
            with self.monitor.phase("firmware_modification"):
                self.reporter.on_phase_start("Firmware Modification")
                FirmwareModifier(self.ctx).run()
                self.reporter.on_phase_end("Firmware Modification", True, 0)

            # Phase 5: ROM Modification
            with self.monitor.phase("rom_modification"):
                self.reporter.on_phase_start("ROM Modification")
                RomModifier(self.ctx).run_all_modifications()
                self.reporter.on_phase_end("ROM Modification", True, 0)

            # Phase 6: App Patching
            with self.monitor.phase("app_patching"):
                self.reporter.on_phase_start("App Patching")
                apk_modifier = ApkModifier(self.ctx)
                apk_modifier.run()
                self.reporter.on_phase_end("App Patching", True, 0)

            # Phase 7: Repacking
            with self.monitor.phase("repacking"):
                self.reporter.on_phase_start("Repacking")

                packer = Repacker(self.ctx)
                packer.pack_all()

                # Determine packing strategy
                if getattr(self.ctx, "pack_type", "payload") == "super":
                    packer.pack_super_image()
                else:
                    packer.pack_ota_payload()

                self.reporter.on_phase_end("Repacking", True, 0)

            success = True

        except Exception as e:
            success = False
            self.monitor.report.add_error("porting", e)
            raise

        finally:
            # Always generate report
            self.monitor.stop()
            self.monitor.save_report(self.report_path)
            self.monitor.print_report()

        return success


def run_monitored_porting(context: PortingContext, report_path: Optional[Path] = None) -> bool:
    """Run ROM porting with full monitoring.

    This is a convenience function for running the porting process
    with monitoring enabled.

    Args:
        context: The porting context
        report_path: Optional path to save the monitoring report

    Returns:
        bool: True if successful

    Example:
        ctx = PortingContext(stock_rom, port_rom, target_dir)
        success = run_monitored_porting(ctx, Path("my_report.json"))
    """
    workflow = MonitoredPortingWorkflow(context, report_path)
    return workflow.run()
