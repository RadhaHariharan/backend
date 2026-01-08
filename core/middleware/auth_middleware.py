from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError
from typing import List
import contextvars

from core.config import settings
from utils.response import HttpError

# --- Context vars to hold request-specific token data ---
accessTokenData: contextvars.ContextVar[dict] = contextvars.ContextVar("accessTokenData", default={})
refreshTokenData: contextvars.ContextVar[dict] = contextvars.ContextVar("refreshTokenData", default={})

class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to:
    - Decode access & refresh tokens
    - Set accessTokenData and refreshTokenData
    - Automatically handle public routes and refresh-token-only routes
    """

    def __init__(self, app, public_routes: List[str] = None, refresh_token_only_routes: List[str] = None):
        super().__init__(app)
        self.public_routes = public_routes or []
        self.refresh_token_only_routes = refresh_token_only_routes or []

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # --- Skip public routes ---
        if any(path.startswith(route) for route in self.public_routes):
            return await call_next(request)

        # --- Refresh-token-only routes ---
        if any(path.startswith(route) for route in self.refresh_token_only_routes):
            refresh_token = request.headers.get("Authorization", "").replace("Bearer ", "")
            if not refresh_token:
                raise HttpError(401, "Missing refresh token", "UNAUTHORIZED")
            try:
                payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
                refreshTokenData.set(payload)
            except JWTError:
                raise HttpError(401, "Invalid refresh token", "INVALID_TOKEN")
            return await call_next(request)

        # --- Access-token-required routes ---
        access_token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not access_token:
            raise HttpError(401, "Missing access token", "UNAUTHORIZED")
        try:
            payload = jwt.decode(access_token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            accessTokenData.set(payload)
        except JWTError:
            raise HttpError(401, "Invalid access token", "INVALID_TOKEN")

        return await call_next(request)
