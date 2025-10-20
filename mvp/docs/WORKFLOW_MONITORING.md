# Workflow Monitoring & Notification Framework

Comprehensive logging and notification system for multi-agent clinical data extraction workflows.

## Features

### 1. Multi-Level Logging
- **Console**: Human-readable real-time output
- **File**: Detailed debug logs with line numbers
- **JSON**: Machine-readable structured logs (`.jsonl` format)

### 2. Error Tracking
- Categorized error severity (INFO, WARNING, ERROR, CRITICAL)
- Stack trace capture
- Context preservation (patient ID, phase, timestamp)
- Error metrics and aggregation

### 3. Workflow Metrics
- Progress tracking by phase
- Extraction success/failure counts
- Performance metrics
- Comprehensive summary reports

### 4. Notification Channels
- **Email**: SMTP-based alerts
- **Slack**: Webhook notifications
- **Generic Webhook**: Custom integrations
- Configurable notification thresholds

## Quick Start

### Basic Usage

```python
from utils.workflow_monitoring import WorkflowLogger
from pathlib import Path

# Initialize logger
logger = WorkflowLogger(
    workflow_name="patient_abstraction",
    log_dir=Path("logs/workflow_runs"),
    patient_id="patient123",
    enable_json=True,
    enable_notifications=False
)

# Log messages
logger.log_info("Starting extraction", context={"source": "imaging"})
logger.log_warning("Missing data field", context={"field": "tumor_size"})
logger.log_error(
    "Extraction failed",
    error_type="MedGemmaTimeout",
    stack_trace=traceback.format_exc(),
    notify=True
)

# Track progress
logger.update_phase("temporal_validation")
logger.record_extraction(success=True)

# Save metrics
logger.save_metrics()

# Print summary
print(logger.get_summary())
```

### With Notifications

```python
from utils.workflow_monitoring import WorkflowLogger, NotificationService
from pathlib import Path
import json

# Load notification config
with open("config/notification_config.json") as f:
    notification_config = json.load(f)

# Initialize logger with notifications
logger = WorkflowLogger(
    workflow_name="patient_abstraction",
    log_dir=Path("logs/workflow_runs"),
    patient_id="patient123",
    enable_json=True,
    enable_notifications=True
)

# Initialize notification service
notifier = NotificationService(notification_config)

# Send Slack alert
try:
    notifier.send_slack(
        message="🚨 Critical workflow error detected!",
        channel="#data-alerts"
    )
except Exception as e:
    logger.log_error(f"Failed to send notification: {e}")
```

## Configuration

### 1. Copy Example Config

```bash
cp config/notification_config.example.json config/notification_config.json
```

### 2. Edit Configuration

Edit `config/notification_config.json`:

```json
{
  "email": {
    "enabled": true,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "from_address": "alerts@yourorg.com",
    "recipients": ["team@yourorg.com"]
  },
  "slack": {
    "enabled": true,
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK",
    "channel": "#workflow-alerts",
    "notify_on": ["error", "critical"]
  }
}
```

### 3. Set Environment Variables (Optional)

For sensitive credentials:

```bash
export SMTP_PASSWORD="your-app-password"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
```

## Log Output Formats

### Console Log
```
2025-10-20 09:00:30 - patient_abstraction_console - INFO - Starting extraction
2025-10-20 09:00:35 - patient_abstraction_console - WARNING - Missing field: tumor_size
2025-10-20 09:00:40 - patient_abstraction_console - ERROR - Extraction failed: MedGemmaTimeout
```

### File Log (`.log`)
```
2025-10-20 09:00:30 - patient_abstraction_file - INFO - [run_full_multi_source_abstraction.py:342] - Starting extraction
2025-10-20 09:00:35 - patient_abstraction_file - WARNING - [medgemma_agent.py:156] - Missing field: tumor_size
2025-10-20 09:00:40 - patient_abstraction_file - ERROR - [medgemma_agent.py:178] - Extraction failed: MedGemmaTimeout
Stack trace:
Traceback (most recent call last):
  File "agents/medgemma_agent.py", line 178
  ...
```

### JSON Log (`.jsonl`)
```json
{"timestamp": "2025-10-20T09:00:30", "workflow": "patient_abstraction", "patient_id": "patient123", "level": "info", "phase": "extraction", "message": "Starting extraction", "context": {"source": "imaging"}}
{"timestamp": "2025-10-20T09:00:35", "workflow": "patient_abstraction", "patient_id": "patient123", "level": "warning", "phase": "extraction", "message": "Missing field: tumor_size", "context": {"field": "tumor_size"}}
```

### Metrics File (`_metrics.json`)
```json
{
  "workflow_id": "patient_abstraction_20251020_090030",
  "patient_id": "patient123",
  "start_time": "2025-10-20T09:00:30",
  "current_phase": "temporal_validation",
  "phases_completed": ["data_query", "extraction"],
  "total_extractions": 82,
  "successful_extractions": 79,
  "failed_extractions": 3,
  "errors": [
    {
      "timestamp": "2025-10-20T09:00:40",
      "severity": "error",
      "phase": "extraction",
      "error_type": "MedGemmaTimeout",
      "error_message": "Extraction timed out after 30s",
      "patient_id": "patient123"
    }
  ]
}
```

## Error Severity Levels

| Level | When to Use | Notification |
|-------|-------------|--------------|
| **INFO** | Normal operation progress | No |
| **WARNING** | Recoverable issues, missing optional data | Optional |
| **ERROR** | Failed extraction, retryable errors | Yes (configurable) |
| **CRITICAL** | Workflow failure, data corruption | Always |

## Notification Examples

### Email Alert

Subject: `🚨 Workflow Error Alert: patient_abstraction`

```
Workflow: patient_abstraction
Patient: patient123
Severity: ERROR
Phase: extraction
Time: 2025-10-20T09:00:40

Error Type: MedGemmaTimeout
Message: Extraction timed out after 30s

Context:
{
  "report_id": "imaging_001",
  "attempt": 3
}
```

### Slack Message

```
🚨 Workflow Error Alert

Workflow: patient_abstraction
Patient: patient123
Severity: ERROR
Phase: extraction

Error: MedGemmaTimeout - Extraction timed out after 30s
```

## Integration with Existing Workflows

### Update `run_full_multi_source_abstraction.py`

Replace manual logging with `WorkflowLogger`:

```python
from utils.workflow_monitoring import WorkflowLogger
import traceback

# Initialize
logger = WorkflowLogger(
    workflow_name="multi_source_abstraction",
    log_dir=output_dir / "logs",
    patient_id=args.patient_id,
    enable_json=True,
    enable_notifications=True
)

try:
    # Phase 1: Data Query
    logger.update_phase("data_query")
    logger.log_info("Querying Athena for imaging reports")

    imaging_reports = query_athena(imaging_query)
    logger.log_info(f"Retrieved {len(imaging_reports)} imaging reports")

    # Phase 2: Extraction
    logger.update_phase("extraction")

    for report in imaging_reports:
        try:
            result = medgemma.extract(prompt)
            logger.record_extraction(success=True)
        except Exception as e:
            logger.log_error(
                f"Extraction failed for report {report['id']}",
                error_type=type(e).__name__,
                stack_trace=traceback.format_exc(),
                context={"report_id": report['id']},
                notify=True
            )
            logger.record_extraction(success=False)

    # Save metrics
    logger.save_metrics()
    print(logger.get_summary())

except Exception as e:
    logger.log_critical(
        "Workflow failed with critical error",
        error_type=type(e).__name__,
        stack_trace=traceback.format_exc()
    )
    raise
```

## Monitoring Dashboard (Future)

The JSON logs can be ingested into monitoring tools:

- **ELK Stack**: Elasticsearch + Kibana dashboards
- **Grafana**: Real-time metrics visualization
- **CloudWatch**: AWS-native monitoring
- **Datadog**: Full observability platform

Example Elasticsearch query:
```json
GET workflow_logs/_search
{
  "query": {
    "bool": {
      "must": [
        {"term": {"workflow": "patient_abstraction"}},
        {"term": {"level": "error"}},
        {"range": {"timestamp": {"gte": "now-1h"}}}
      ]
    }
  }
}
```

## Best Practices

1. **Always initialize logger at workflow start**
   - Captures all errors from beginning
   - Provides complete audit trail

2. **Use appropriate severity levels**
   - Don't overuse CRITICAL (alert fatigue)
   - Use WARNING for expected issues

3. **Include context in error logs**
   - Patient ID, report ID, phase
   - Helps with debugging

4. **Save metrics at workflow end**
   - Even if workflow fails
   - Provides failure analytics

5. **Test notifications before production**
   - Verify email/Slack delivery
   - Check alert formatting

6. **Configure notification thresholds**
   - Avoid alert spam
   - Balance sensitivity vs. noise

## Troubleshooting

### Issue: Notifications not sending

**Check:**
1. Configuration file loaded correctly
2. Network connectivity to SMTP/Slack
3. Credentials valid and not expired
4. Webhook URLs correct

**Debug:**
```python
logger = WorkflowLogger(..., enable_notifications=True)
logger.log_error("Test error", notify=True)
# Check console for notification errors
```

### Issue: Logs not written to file

**Check:**
1. Log directory exists and is writable
2. Disk space available
3. File permissions correct

**Debug:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
# Will show logging system errors
```

### Issue: JSON logs malformed

**Check:**
1. Context objects are JSON-serializable
2. No circular references in context
3. Datetime objects converted to strings

**Fix:**
```python
# Convert non-serializable objects
context = {
    "timestamp": datetime.now().isoformat(),  # ✅
    "data": json.dumps(complex_obj)  # ✅
}
logger.log_info("Message", context=context)
```

## API Reference

See [workflow_monitoring.py](../utils/workflow_monitoring.py) for complete API documentation.

### Key Classes

- `WorkflowLogger`: Main logging interface
- `NotificationService`: Multi-channel notifications
- `WorkflowError`: Structured error data
- `WorkflowMetrics`: Performance metrics

### Key Methods

- `log_info()`, `log_warning()`, `log_error()`, `log_critical()`
- `update_phase()`
- `record_extraction()`
- `save_metrics()`
- `get_summary()`
