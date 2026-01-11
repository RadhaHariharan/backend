import uvicorn
from fastapi import FastAPI, Request
from api.v1 import router as v1_router
from api.v1.routes.organizations import router as org_router
from api.v1.routes.roles import router as role_router
from core.exception_handlers import setup_exception_handlers, logger
from core.middleware.auth_middleware import AuthMiddleware
from core.middleware.tenant_middleware import TenantMiddleware
from core.config import settings
from utils.response import send_error_response

setup_exception_handlers()
app = FastAPI()

# --- Public routes (no auth required) ---
public_routes = [
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/openapi.json",
    "/docs",
    "/redoc"
]

# Routes that don't require orgId in token
# (user must be authenticated but org is optional)
org_optional_routes = [
    "/api/v1/organizations",
    "/api/v1/auth/refresh"
]

refresh_token_only_routes = []

# --- Middleware (ORDER MATTERS!) ---
# 1. Authentication first (validates token, sets accessTokenData)
app.add_middleware(
    AuthMiddleware,
    public_routes=public_routes,
    refresh_token_only_routes=refresh_token_only_routes
)

# 2. Tenant middleware (reads orgId from token, sets currentOrg)
# Runs after auth so it can access token data
app.add_middleware(
    TenantMiddleware,
    public_routes=public_routes + org_optional_routes
)

# --- Global exception handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(
        f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}"
    )
    return send_error_response(exc)

# --- API Routes ---
app.include_router(org_router, prefix="/api/v1")   # Org management (public schema)
app.include_router(role_router, prefix="/api/v1")  # Roles (tenant schema)
app.include_router(v1_router, prefix="/api/v1")    # Auth routes

if __name__ == "__main__":
    logger.debug("Starting server...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=(settings.ENVIRONMENT == "development")
    )