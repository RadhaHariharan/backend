from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from services.auth_service import AuthService
from utils.response import send_custom_response, HttpError

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)

@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Async Login endpoint:
    - verifies email & password
    - returns access + refresh tokens
    - uses centralized response structure
    """
    auth_service = AuthService(db)

    try:
        tokens = await auth_service.login(
            email=payload.email,
            password=payload.password
        )
        # --- Success response ---
        return send_custom_response(tokens, success_message="Login successful")

    except ValueError:
        # --- Invalid credentials ---
        raise HttpError(401, "Invalid email or password", "INVALID_CREDENTIALS")
    except Exception as e:
        # --- Any other unexpected error ---
        raise HttpError(500, "Internal Server Error", str(e))


@router.post("/register", response_model=UserResponse)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Register endpoint:
    - Creates a new user account
    - Validates email is not already registered
    - Hashes password securely
    - Returns user details
    """
    auth_service = AuthService(db)

    try:
        user = await auth_service.register(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            password=payload.password
        )
        # --- Success response ---
        return send_custom_response(user, success_message="User registered successfully")

    except ValueError as e:
        # --- Email already registered ---
        raise HttpError(400, str(e), "EMAIL_ALREADY_REGISTERED")
    except Exception as e:
        # --- Any other unexpected error ---
        raise HttpError(500, "Internal Server Error", str(e))
