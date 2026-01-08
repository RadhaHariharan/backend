from core.middleware.auth_middleware import accessTokenData, refreshTokenData
from utils.response import HttpError


def get_current_user_access_token() -> dict:
    """
    Returns the decoded payload from the access token.
    Raises HttpError if not found.
    """
    payload = accessTokenData.get()
    if not payload:
        raise HttpError(401, "No access token found", "UNAUTHORIZED")
    return payload


def get_current_user_refresh_token() -> dict:
    """
    Returns the decoded payload from the refresh token.
    Raises HttpError if not found.
    """
    payload = refreshTokenData.get()
    if not payload:
        raise HttpError(401, "No refresh token found", "UNAUTHORIZED")
    return payload
