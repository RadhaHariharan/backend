import sys
import threading
from core.logger import logger


def handle_exception(exc_type, exc_value, exc_traceback):
    """
    Handle uncaught exceptions in the main thread
    
    Args:
        exc_type: The exception type
        exc_value: The exception instance
        exc_traceback: The traceback object
    """
    # Ignore KeyboardInterrupt (Ctrl+C)
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    # Log the exception with full traceback
    try:
        raise exc_value.with_traceback(exc_traceback)
    except exc_type:
        logger.exception("Uncaught Python exception in main thread")


def handle_thread_exception(args):
    """
    Handle uncaught exceptions in threads (Python 3.8+)
    
    Args:
        args: threading.ExceptHookArgs containing:
            - exc_type: The exception type
            - exc_value: The exception instance
            - exc_traceback: The traceback object
            - thread: The thread object
    """
    try:
        raise args.exc_value.with_traceback(args.exc_traceback)
    except args.exc_type:
        logger.exception(f"Uncaught exception in thread '{args.thread.name}'")


def setup_exception_handlers():
    """
    Register global exception handlers for Python-level exceptions
    
    This should be called early in your application startup,
    typically in main.py before creating the FastAPI app.
    """
    sys.excepthook = handle_exception
    threading.excepthook = handle_thread_exception
    logger.info("Global Python exception handlers registered")


# Convenience function to unregister handlers (for testing)
def teardown_exception_handlers():
    """
    Restore default exception handlers
    """
    sys.excepthook = sys.__excepthook__
    threading.excepthook = threading.__excepthook__
    logger.info("Global Python exception handlers unregistered")