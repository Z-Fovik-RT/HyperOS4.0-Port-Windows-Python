"""
# ROM Modification Monitoring System

Comprehensive monitoring and observability for ROM modifications.

## Features

- **Structured Logging**: JSON-formatted logs with context
- **Performance Metrics**: Track execution time, file operations, resource usage
- **Execution Tracing**: Hierarchical operation tracking with call trees
- **Progress Tracking**: Real-time progress bars and spinners
- **Error Reporting**: Detailed error context and stack traces
- **Console UI**: Beautiful terminal output with animations
- **Plugin Integration**: Built-in monitoring for modifier plugins
- **Report Generation**: JSON and human-readable reports

## Quick Start

### Basic Monitoring

```python
from src.core.monitoring import Monitor

monitor = Monitor()
monitor.start()

# Monitor a phase
with monitor.phase("extraction"):
    # Your code here
    rom.extract()
    monitor.record_metric("files_extracted", 150)

monitor.stop()
monitor.print_report()
```

### With Plugins

```python
from src.core.monitoring.plugin_integration import MonitoredPlugin

class MyPlugin(MonitoredPlugin):
    name = "my_plugin"
    
    def _do_modify(self) -> bool:
        self.record_metric("items_processed", 42)
        return True

# Plugin automatically reports metrics
```

### Progress Tracking

```python
from src.core.monitoring import get_monitor
from src.core.monitoring.console_ui import ConsoleReporter

monitor = get_monitor()
reporter = ConsoleReporter()
monitor.add_progress_listener(reporter.on_progress_update)

for i in range(total):
    monitor.update_progress(i + 1, f"Step {i+1}")
    # Do work
```

## Components

### Monitor

Main interface coordinating all monitoring:
- Phase tracking
- Metrics collection
- Progress updates
- Report generation

### MetricsCollector

Collects and manages performance metrics:
- Counter increments
- Gauge values
- Time series data

### ExecutionTracer

Traces operation execution:
- Call trees
- Duration tracking
- Success/failure tracking

### ProgressTracker

Tracks progress of long operations:
- Percentage calculation
- ETA estimation
- Event listeners

### ConsoleReporter

Real-time console output:
- Progress bars
- Spinners
- Status icons

## Configuration

Monitoring is enabled by default. To customize:

```python
monitor = Monitor()
monitor.add_progress_listener(my_callback)
monitor.start()
```

## Report Format

JSON report structure:

```json
{
  "report_type": "rom_modification_monitoring",
  "version": "1.0",
  "duration_seconds": 123.45,
  "summary": {
    "phases_completed": 7,
    "phases_failed": 0,
    "total_errors": 0
  },
  "metrics": {
    "counters": {
      "files_copied": 150,
      "bytes_copied": 104857600
    }
  },
  "execution_trace": {
    "operations": [...],
    "summary": {...}
  },
  "phase_results": {...},
  "errors": [...]
}
```

## Examples

See `examples/monitoring_example.py` for complete examples.

## Integration with Main Workflow

```python
from src.core.monitoring.workflow_integration import run_monitored_porting

ctx = PortingContext(stock, port, target_dir)
success = run_monitored_porting(ctx, Path("report.json"))
```

## Metrics Reference

### System Metrics
- `files_extracted`: Number of files extracted
- `bytes_extracted`: Total bytes extracted
- `files_copied`: Number of files copied
- `bytes_copied`: Total bytes copied
- `images_processed`: Number of partition images processed

### Plugin Metrics
- `plugin.{name}.attempts`: Plugin execution attempts
- `plugin.{name}.successes`: Successful executions
- `plugin.{name}.failures`: Failed executions
- `plugin.{name}.duration`: Execution duration

### Phase Metrics
- `phase.{name}.duration`: Phase execution time
- `phase.{name}.completed`: Completion status

## License

Same as the main project.
"""

__version__ = "1.0.0"

from src.core.monitoring.__init__ import (
    Monitor,
    MetricsCollector,
    ExecutionTracer,
    ProgressTracker,
    MonitoringReport,
    MetricPoint,
    OperationRecord,
    get_monitor,
    set_monitor,
    reset_monitor,
    monitored,
)

__all__ = [
    'Monitor',
    'MetricsCollector',
    'ExecutionTracer',
    'ProgressTracker',
    'MonitoringReport',
    'MetricPoint',
    'OperationRecord',
    'get_monitor',
    'set_monitor',
    'reset_monitor',
    'monitored',
]
