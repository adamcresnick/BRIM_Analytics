"""
Workflow Monitoring and Notification Framework

Provides comprehensive logging, error tracking, and notification capabilities
for multi-agent clinical data extraction workflows.

Features:
- Structured logging with multiple handlers (console, file, JSON)
- Error tracking and categorization
- Notification system (email, Slack, webhook)
- Progress tracking and metrics
- Automatic alerting on critical errors
"""

import logging
import json
import smtplib
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class ErrorSeverity(Enum):
    """Error severity levels for alerting"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class NotificationChannel(Enum):
    """Available notification channels"""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    LOG_ONLY = "log_only"


@dataclass
class WorkflowError:
    """Structured error information"""
    timestamp: str
    severity: ErrorSeverity
    phase: str
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    patient_id: Optional[str] = None


@dataclass
class WorkflowMetrics:
    """Workflow progress and performance metrics"""
    workflow_id: str
    patient_id: str
    start_time: str
    current_phase: str
    phases_completed: List[str]
    total_extractions: int
    successful_extractions: int
    failed_extractions: int
    errors: List[WorkflowError]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            **asdict(self),
            'errors': [asdict(e) for e in self.errors]
        }


class WorkflowLogger:
    """
    Enhanced logging with structured output and notifications.

    Features:
    - Console logging (human-readable)
    - File logging (detailed)
    - JSON logging (machine-readable for monitoring)
    - Error tracking and metrics
    """

    def __init__(
        self,
        workflow_name: str,
        log_dir: Path,
        patient_id: str,
        enable_json: bool = True,
        enable_notifications: bool = False
    ):
        self.workflow_name = workflow_name
        self.log_dir = Path(log_dir)
        self.patient_id = patient_id
        self.enable_json = enable_json
        self.enable_notifications = enable_notifications

        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Initialize timestamp for log files
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Setup loggers
        self.logger = self._setup_console_logger()
        self.file_logger = self._setup_file_logger()
        if enable_json:
            self.json_logger = self._setup_json_logger()

        # Metrics tracking
        self.metrics = WorkflowMetrics(
            workflow_id=f"{workflow_name}_{self.timestamp}",
            patient_id=patient_id,
            start_time=datetime.now().isoformat(),
            current_phase="initialization",
            phases_completed=[],
            total_extractions=0,
            successful_extractions=0,
            failed_extractions=0,
            errors=[]
        )

    def _setup_console_logger(self) -> logging.Logger:
        """Setup console logger for human-readable output"""
        logger = logging.getLogger(f"{self.workflow_name}_console")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        return logger

    def _setup_file_logger(self) -> logging.Logger:
        """Setup detailed file logger"""
        logger = logging.getLogger(f"{self.workflow_name}_file")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()

        log_file = self.log_dir / f"{self.workflow_name}_{self.timestamp}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        return logger

    def _setup_json_logger(self) -> logging.Logger:
        """Setup JSON logger for machine-readable structured logs"""
        logger = logging.getLogger(f"{self.workflow_name}_json")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()

        json_log_file = self.log_dir / f"{self.workflow_name}_{self.timestamp}.jsonl"
        json_handler = logging.FileHandler(json_log_file)
        json_handler.setLevel(logging.INFO)

        # No formatter - we'll write raw JSON
        logger.addHandler(json_handler)

        return logger

    def log_info(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log informational message"""
        self.logger.info(message)
        self.file_logger.info(message)

        if self.enable_json:
            self._log_json("info", message, context)

    def log_warning(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log warning message"""
        self.logger.warning(message)
        self.file_logger.warning(message)

        if self.enable_json:
            self._log_json("warning", message, context)

        # Track warning
        error = WorkflowError(
            timestamp=datetime.now().isoformat(),
            severity=ErrorSeverity.WARNING,
            phase=self.metrics.current_phase,
            error_type="warning",
            error_message=message,
            context=context,
            patient_id=self.patient_id
        )
        self.metrics.errors.append(error)

    def log_error(
        self,
        message: str,
        error_type: str = "unknown",
        stack_trace: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        notify: bool = True
    ):
        """Log error message with optional notification"""
        self.logger.error(message)
        self.file_logger.error(message)
        if stack_trace:
            self.file_logger.error(f"Stack trace:\n{stack_trace}")

        if self.enable_json:
            self._log_json("error", message, context, stack_trace)

        # Track error
        error = WorkflowError(
            timestamp=datetime.now().isoformat(),
            severity=ErrorSeverity.ERROR,
            phase=self.metrics.current_phase,
            error_type=error_type,
            error_message=message,
            stack_trace=stack_trace,
            context=context,
            patient_id=self.patient_id
        )
        self.metrics.errors.append(error)
        self.metrics.failed_extractions += 1

        # Send notification if enabled
        if notify and self.enable_notifications:
            self._send_error_notification(error)

    def log_critical(
        self,
        message: str,
        error_type: str = "critical",
        stack_trace: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """Log critical error and always send notification"""
        self.logger.critical(message)
        self.file_logger.critical(message)
        if stack_trace:
            self.file_logger.critical(f"Stack trace:\n{stack_trace}")

        if self.enable_json:
            self._log_json("critical", message, context, stack_trace)

        # Track critical error
        error = WorkflowError(
            timestamp=datetime.now().isoformat(),
            severity=ErrorSeverity.CRITICAL,
            phase=self.metrics.current_phase,
            error_type=error_type,
            error_message=message,
            stack_trace=stack_trace,
            context=context,
            patient_id=self.patient_id
        )
        self.metrics.errors.append(error)

        # Always notify on critical errors
        if self.enable_notifications:
            self._send_error_notification(error)

    def _log_json(
        self,
        level: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        stack_trace: Optional[str] = None
    ):
        """Write structured JSON log entry"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "workflow": self.workflow_name,
            "patient_id": self.patient_id,
            "level": level,
            "phase": self.metrics.current_phase,
            "message": message,
            "context": context or {},
            "stack_trace": stack_trace
        }

        self.json_logger.info(json.dumps(log_entry))

    def update_phase(self, phase: str):
        """Update current workflow phase"""
        self.metrics.phases_completed.append(self.metrics.current_phase)
        self.metrics.current_phase = phase
        self.log_info(f"Entering phase: {phase}")

    def record_extraction(self, success: bool):
        """Record extraction attempt"""
        self.metrics.total_extractions += 1
        if success:
            self.metrics.successful_extractions += 1
        else:
            self.metrics.failed_extractions += 1

    def save_metrics(self, output_path: Optional[Path] = None):
        """Save workflow metrics to JSON file"""
        if output_path is None:
            output_path = self.log_dir / f"{self.workflow_name}_{self.timestamp}_metrics.json"

        with open(output_path, 'w') as f:
            json.dump(self.metrics.to_dict(), f, indent=2)

        self.log_info(f"Metrics saved to: {output_path}")

    def _send_error_notification(self, error: WorkflowError):
        """Send error notification via configured channels"""
        # This is a placeholder - implement based on your notification preferences
        # Examples: email, Slack webhook, PagerDuty, etc.

        notification_message = self._format_error_notification(error)

        # Log that notification would be sent
        self.log_info(f"[NOTIFICATION] {error.severity.value.upper()}: {error.error_message}")

        # TODO: Implement actual notification sending
        # Example: self._send_slack_notification(notification_message)
        # Example: self._send_email_notification(notification_message)

    def _format_error_notification(self, error: WorkflowError) -> str:
        """Format error for notification"""
        return f"""
🚨 Workflow Error Alert

Workflow: {self.workflow_name}
Patient: {error.patient_id}
Severity: {error.severity.value.upper()}
Phase: {error.phase}
Time: {error.timestamp}

Error Type: {error.error_type}
Message: {error.error_message}

Context: {json.dumps(error.context, indent=2) if error.context else 'None'}
"""

    def get_summary(self) -> str:
        """Get workflow summary"""
        success_rate = (
            100 * self.metrics.successful_extractions / self.metrics.total_extractions
            if self.metrics.total_extractions > 0 else 0
        )

        return f"""
Workflow Summary: {self.workflow_name}
Patient: {self.patient_id}
Start Time: {self.metrics.start_time}
Current Phase: {self.metrics.current_phase}
Phases Completed: {', '.join(self.metrics.phases_completed)}

Extractions:
  Total: {self.metrics.total_extractions}
  Successful: {self.metrics.successful_extractions}
  Failed: {self.metrics.failed_extractions}
  Success Rate: {success_rate:.1f}%

Errors:
  Total: {len(self.metrics.errors)}
  Warnings: {sum(1 for e in self.metrics.errors if e.severity == ErrorSeverity.WARNING)}
  Errors: {sum(1 for e in self.metrics.errors if e.severity == ErrorSeverity.ERROR)}
  Critical: {sum(1 for e in self.metrics.errors if e.severity == ErrorSeverity.CRITICAL)}
"""


class NotificationService:
    """
    Notification service for sending alerts via multiple channels.

    Supported channels:
    - Email (SMTP)
    - Slack (webhook)
    - Generic webhook
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    def send_email(
        self,
        subject: str,
        body: str,
        to_addresses: List[str],
        smtp_config: Optional[Dict[str, Any]] = None
    ):
        """Send email notification"""
        config = smtp_config or self.config.get('email', {})

        if not config:
            raise ValueError("Email configuration not provided")

        msg = MIMEMultipart()
        msg['From'] = config['from_address']
        msg['To'] = ', '.join(to_addresses)
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        try:
            with smtplib.SMTP(config['smtp_host'], config['smtp_port']) as server:
                if config.get('use_tls', True):
                    server.starttls()
                if 'username' in config:
                    server.login(config['username'], config['password'])
                server.send_message(msg)
        except Exception as e:
            raise RuntimeError(f"Failed to send email: {e}")

    def send_slack(
        self,
        message: str,
        webhook_url: Optional[str] = None,
        channel: Optional[str] = None
    ):
        """Send Slack notification via webhook"""
        url = webhook_url or self.config.get('slack', {}).get('webhook_url')

        if not url:
            raise ValueError("Slack webhook URL not provided")

        payload = {
            'text': message,
            'username': 'Workflow Monitor',
            'icon_emoji': ':robot_face:'
        }

        if channel:
            payload['channel'] = channel

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"Failed to send Slack notification: {e}")

    def send_webhook(
        self,
        data: Dict[str, Any],
        webhook_url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        """Send generic webhook notification"""
        url = webhook_url or self.config.get('webhook', {}).get('url')

        if not url:
            raise ValueError("Webhook URL not provided")

        try:
            response = requests.post(
                url,
                json=data,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"Failed to send webhook: {e}")


# Configuration example
NOTIFICATION_CONFIG_EXAMPLE = {
    'email': {
        'smtp_host': 'smtp.gmail.com',
        'smtp_port': 587,
        'use_tls': True,
        'from_address': 'alerts@example.com',
        'username': 'alerts@example.com',
        'password': 'your-password',
        'recipients': ['admin@example.com']
    },
    'slack': {
        'webhook_url': 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL',
        'channel': '#workflow-alerts'
    },
    'webhook': {
        'url': 'https://your-monitoring-service.com/webhook',
        'headers': {'Authorization': 'Bearer YOUR_TOKEN'}
    }
}
