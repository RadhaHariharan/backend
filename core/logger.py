"""
Centralized logging configuration using Loguru
Place this file in: core/logger.py

Install required package:
pip install loguru
"""

import sys
from pathlib import Path
from loguru import logger

from core.config import settings

# Get environment
ENV = settings.ENVIRONMENT
LOG_LEVEL = "DEBUG"

# Create logs directory if it doesn't exist
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

# Remove default handler
logger.remove()

# Console handler with color and formatting
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=LOG_LEVEL,
    colorize=True,
    backtrace=True,
    diagnose=True,
)

# File handler - General logs (with rotation)
logger.add(
    LOGS_DIR / "app_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level=LOG_LEVEL,
    rotation="5 MB",
    retention="30 days",
    compression="zip",
    backtrace=True,
    diagnose=True,
)

# File handler - Error logs only
logger.add(
    LOGS_DIR / "error_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="ERROR",
    rotation="5 MB",
    retention="90 days",
    compression="zip",
    backtrace=True,
    diagnose=True,
)

# JSON handler for production (machine-readable logs)
if ENV == "production":
    logger.add(
        LOGS_DIR / "app_json_{time:YYYY-MM-DD}.log",
        level="INFO",
        rotation="5 MB",
        retention="30 days",
        compression="zip",
        serialize=True,
    )


# Helper function to get a logger with context
def get_logger(name: str = None):
    """
    Get a logger instance with optional context name
    
    Usage:
        from core.logger import get_logger
        logger = get_logger(__name__)
        logger.info("This is an info message")
    """
    if name:
        return logger.bind(name=name)
    return logger


# Convenience function to log API requests
def log_request(method: str, path: str, status_code: int, duration: float):
    """
    Log API request details
    
    Usage:
        log_request("GET", "/api/v1/users", 200, 0.123)
    """
    logger.info(
        f"API Request: {method} {path} - Status: {status_code} - Duration: {duration:.3f}s"
    )


# Convenience function to log database queries
def log_query(query: str, duration: float, params: dict = None):
    """
    Log database query execution
    
    Usage:
        log_query("SELECT * FROM users WHERE id = ?", 0.05, {"id": 123})
    """
    logger.debug(
        f"DB Query executed in {duration:.3f}s: {query[:100]}..." 
        + (f" | Params: {params}" if params else "")
    )


# Exception logging helper
def log_exception(exc: Exception, context: str = None):
    """
    Log exception with full traceback
    
    Usage:
        try:
            # some code
        except Exception as e:
            log_exception(e, "User registration failed")
    """
    if context:
        logger.exception(f"{context}: {str(exc)}")
    else:
        logger.exception(f"Exception occurred: {str(exc)}")


# Export the configured logger
__all__ = ["logger", "get_logger", "log_request", "log_query", "log_exception"]