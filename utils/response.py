from fastapi.responses import JSONResponse
from fastapi import status
from typing import Any


class HttpError(Exception):
    """
    Custom exception for HTTP errors
    """
    def __init__(self, status_code: int, message: str, error_code: str = ""):
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        super().__init__(message)


def send_custom_response(result: Any = None, *, success_message: str = "Success", status_code: int = 200):
    """
    Unified success response
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "message": success_message,
            "statusCode": status_code,
            "result": result
        }
    )


def send_error_response(err: Exception):
    """
    Unified error response
    """
    if isinstance(err, HttpError):
        return JSONResponse(
            status_code=err.status_code,
            content={
                "message": err.message,
                "statusCode": err.status_code,
                "error": err.error_code
            }
        )
    else:
        # generic unhandled exception
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "message": "Internal Server Error",
                "statusCode": 500,
                "error": str(err)
            }
        )
