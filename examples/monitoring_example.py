"""Example: Using the monitoring system with ROM modifications.

This example demonstrates how to integrate monitoring into the ROM porting workflow.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.monitoring import Monitor, get_monitor
from src.core.monitoring.console_ui import ConsoleReporter


def example_basic_monitoring():
    """Basic monitoring example."""
    print("=" * 60)
    print("Example 1: Basic Monitoring")
    print("=" * 60)
    
    # Create monitor
    monitor = Monitor()
    
    # Start monitoring
    monitor.start()
    
    # Monitor a phase
    with monitor.phase("extraction"):
        # Simulate work
        import time
        time.sleep(0.5)
        
        # Record some metrics
        monitor.record_metric("files_extracted", 150)
        monitor.record_metric("bytes_extracted", 1024 * 1024 * 500, "bytes")
    
    # Another phase
    with monitor.phase("modification"):
        time.sleep(0.3)
        monitor.record_metric("patches_applied", 25)
    
    # Stop and print report
    monitor.stop()
    monitor.print_report()
    
    # Save to file
    report_path = Path("/tmp/monitoring_report_example.json")
    monitor.save_report(report_path)
    print(f"Report saved to: {report_path}")


def example_progress_tracking():
    """Progress tracking with console UI."""
    print("\n" + "=" * 60)
    print("Example 2: Progress Tracking")
    print("=" * 60)
    
    monitor = get_monitor()
    monitor.start()
    
    # Setup console reporter
    reporter = ConsoleReporter()
    monitor.add_progress_listener(reporter.on_progress_update)
    
    # Simulate phased work with progress
    with monitor.phase("file_processing"):
        total_files = 10
        
        for i in range(total_files):
            # Update progress
            monitor.update_progress(
                step=i + 1,
                operation=f"Processing file {i+1}/{total_files}"
            )
            
            # Simulate work
            import time
            time.sleep(0.1)
            
            # Record metric
            monitor.record_metric("files_processed", 1)
    
    monitor.stop()


def example_tracing():
    """Execution tracing example."""
    print("\n" + "=" * 60)
    print("Example 3: Execution Tracing")
    print("=" * 60)
    
    monitor = get_monitor()
    monitor.start()
    
    # Create nested operation traces
    with monitor.trace_operation("rom_porting", version="1.0"):
        with monitor.trace_operation("extraction"):
            import time
            time.sleep(0.2)
            
        with monitor.trace_operation("modification"):
            with monitor.trace_operation("framework_patch"):
                time.sleep(0.1)
            with monitor.trace_operation("system_patch"):
                time.sleep(0.15)
    
    monitor.stop()
    
    # Print trace
    trace = monitor.report.execution_tracer.to_dict()
    print("\nExecution Trace:")
    print(f"  Total operations: {trace['summary']['total_operations']}")
    print(f"  Successful: {trace['summary']['successful_operations']}")
    print(f"  Total duration: {trace['summary']['total_duration']:.2f}s")
    
    def print_ops(ops, indent=0):
        for op in ops:
            status = "✓" if op['success'] else "✗"
            print(f"{'  ' * indent}{status} {op['name']}: {op['duration']:.2f}s")
            if op['sub_operations']:
                print_ops(op['sub_operations'], indent + 1)
    
    print("\nOperations:")
    print_ops(trace['operations'])


def example_plugin_monitoring():
    """Monitoring with plugins."""
    print("\n" + "=" * 60)
    print("Example 4: Plugin Monitoring")
    print("=" * 60)
    
    from src.core.monitoring.plugin_integration import MonitoredPlugin, MonitoredPluginManager
    
    # Create a context mock
    class MockContext:
        target_dir = Path("/tmp/mock_target")
        stock_rom_code = "mock_device"
        device_config = {"test": {"enabled": True}}
    
    # Create monitored plugin
    class TestPlugin(MonitoredPlugin):
        name = "test_plugin"
        description = "A test plugin with monitoring"
        priority = 50
        
        def _do_modify(self) -> bool:
            # Record custom metrics
            self.record_metric("items_processed", 42)
            self.record_metric("processing_time", 1.5, "seconds")
            
            # Update progress
            for i in range(5):
                self.update_progress(i + 1, f"Step {i+1}")
                import time
                time.sleep(0.05)
            
            return True
    
    # Setup monitor and manager
    monitor = get_monitor()
    monitor.start()
    
    manager = MonitoredPluginManager(MockContext())
    manager.register(TestPlugin)
    
    # Execute with monitoring
    print("\nExecuting plugins...")
    results = manager.execute()
    
    monitor.stop()
    
    print(f"\nResults: {results}")
    print(f"Metrics collected: {len(monitor.report.metrics_collector.get_metrics())}")


def example_real_world_usage():
    """Real-world usage with the full system."""
    print("\n" + "=" * 60)
    print("Example 5: Real-world Usage")
    print("=" * 60)
    
    print("""
In a real ROM porting scenario, you would use monitoring like this:

    from src.core.monitoring import Monitor, get_monitor
    from src.core.modifiers import SystemModifier, FrameworkModifier
    
    def port_rom(stock_rom, port_rom):
        # Create and start monitor
        monitor = get_monitor()
        monitor.start()
        
        try:
            # Phase 1: Extraction
            with monitor.phase("extraction"):
                stock_rom.extract()
                port_rom.extract()
                monitor.record_metric("images_extracted", 8)
            
            # Phase 2: System Modification
            with monitor.phase("system_modification"):
                modifier = SystemModifier(context)
                modifier.run()  # Automatically monitored
            
            # Phase 3: Framework Modification
            with monitor.phase("framework_modification"):
                fw_modifier = FrameworkModifier(context)
                fw_modifier.run()
            
            # Phase 4: Repacking
            with monitor.phase("repacking"):
                repacker.pack_all()
                monitor.record_metric("images_packed", 8)
        
        except Exception as e:
            monitor.report.add_error("porting", e)
            raise
        
        finally:
            # Always stop and generate report
            monitor.stop()
            monitor.save_report(Path("porting_report.json"))
            monitor.print_report()

The monitoring system automatically tracks:
- Phase execution times
- Success/failure rates
- Custom metrics (files processed, bytes copied, etc.)
- Error details with context
- Plugin execution traces
- Progress updates for UI
""")


if __name__ == "__main__":
    # Run all examples
    example_basic_monitoring()
    example_progress_tracking()
    example_tracing()
    example_plugin_monitoring()
    example_real_world_usage()
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)
