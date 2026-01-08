from fastapi import FastAPI, Request
from api.v1 import router as v1_router
from core.middleware.auth_middleware import AuthMiddleware
from utils.response import send_error_response

app = FastAPI()

# --- Define your routes categories here ---
public_routes = [
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/openapi.json",
    "/docs",
    "/redoc"
]

refresh_token_only_routes = []

# --- Middleware ---
app.add_middleware(
    AuthMiddleware,
    public_routes=public_routes,
    refresh_token_only_routes=refresh_token_only_routes
)

# --- Global exception handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return send_error_response(exc)

# --- API Routes ---
app.include_router(v1_router, prefix="/api/v1")
