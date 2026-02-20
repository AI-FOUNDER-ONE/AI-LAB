"""
logger.py - Unified logging system for AI-Lab-Commander

Features:
- Multiple log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Console and file output
- Configurable log format
- Thread-safe logging
- Integration with existing error handling
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional

from config import DATA_DIR


class AILabLogger:
    """Centralized logger for AI-Lab-Commander."""

    # Log levels
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

    # Singleton instance
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Create logs directory
        self.logs_dir = os.path.join(DATA_DIR, "logs")
        os.makedirs(self.logs_dir, exist_ok=True)

        # Configure root logger
        self._configure_root_logger()

        # Application logger
        self.logger = logging.getLogger("ai_lab")
        self.logger.setLevel(logging.DEBUG)

        self._initialized = True

    def _configure_root_logger(self):
        """Configure the root logger with file and console handlers."""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.WARNING)  # Root captures warnings and above

        # Clear any existing handlers
        root_logger.handlers.clear()

        # Console handler for warnings and above
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    def setup_app_logger(self, log_level: int = logging.INFO,
                         log_to_file: bool = True,
                         max_file_size_mb: int = 10,
                         backup_count: int = 5) -> logging.Logger:
        """Setup application-specific logger.

        Args:
            log_level: Minimum log level to capture
            log_to_file: Whether to log to file
            max_file_size_mb: Maximum log file size in MB before rotation
            backup_count: Number of backup files to keep

        Returns:
            Configured logger instance
        """
        # Clear any existing handlers on the ai_lab logger
        self.logger.handlers.clear()

        # Console handler (always active)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)8s - %(message)s",
            datefmt="%H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # File handler (optional)
        if log_to_file:
            log_file = os.path.join(self.logs_dir, f"ai_lab_{datetime.now().strftime('%Y%m%d')}.log")
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_file_size_mb * 1024 * 1024,  # Convert MB to bytes
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(log_level)
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

        return self.logger

    def debug(self, msg: str, *args, **kwargs):
        """Log debug message."""
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        """Log info message."""
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        """Log warning message."""
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        """Log error message."""
        self.logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        """Log critical message."""
        self.logger.critical(msg, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs):
        """Log exception with traceback."""
        self.logger.exception(msg, *args, **kwargs)

    def log_agent_activity(self, role: str, action: str, details: str = "", level: int = INFO):
        """Log agent activity with standardized format.

        Args:
            role: Agent role (CKO, PM, Arch, etc.)
            action: Action being performed
            details: Additional details
            level: Log level
        """
        message = f"[{role}] {action}"
        if details:
            message += f" - {details}"

        self.logger.log(level, message)

    def log_state_transition(self, from_state: str, to_state: str, reason: str = ""):
        """Log state machine transition.

        Args:
            from_state: Previous state
            to_state: New state
            reason: Reason for transition
        """
        message = f"State transition: {from_state} → {to_state}"
        if reason:
            message += f" ({reason})"

        self.logger.info(message)

    def log_api_call(self, provider: str, endpoint: str, status: str = "", duration_ms: float = None):
        """Log API call details.

        Args:
            provider: API provider (openai, anthropic, etc.)
            endpoint: API endpoint or model name
            status: Call status (success, error, etc.)
            duration_ms: Call duration in milliseconds
        """
        message = f"API: {provider}/{endpoint}"
        if status:
            message += f" - {status}"
        if duration_ms is not None:
            message += f" - {duration_ms:.2f}ms"

        self.logger.debug(message)

    def log_thread_event(self, thread_name: str, event: str, details: str = ""):
        """Log thread-related events.

        Args:
            thread_name: Thread identifier
            event: Event type (started, finished, cancelled, etc.)
            details: Additional details
        """
        message = f"Thread[{thread_name}] {event}"
        if details:
            message += f" - {details}"

        self.logger.debug(message)


# Global logger instance
logger = AILabLogger()


def setup_logging(log_level: int = logging.INFO, **kwargs) -> logging.Logger:
    """Convenience function to setup and return the application logger.

    Args:
        log_level: Minimum log level
        **kwargs: Additional arguments for setup_app_logger

    Returns:
        Configured logger instance
    """
    return logger.setup_app_logger(log_level=log_level, **kwargs)


def get_logger(name: str = "ai_lab") -> logging.Logger:
    """Get a named logger instance.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)