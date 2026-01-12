from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.docs.auth_docs import login_docs, register_docs
from api.deps import get_public_db
from schemas.auth import LoginRequest, RegisterRequest, TokenResponse, RegisterResponse
from services.auth_service import AuthService
from utils.response import send_custom_response, HttpError

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    **login_docs
)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_public_db)
) -> TokenResponse:
    """
    Authenticate user and return access tokens.
    """
    auth_service = AuthService(db)

    try:
        tokens = await auth_service.login(
            email=payload.email,
            password=payload.password
        )
        return send_custom_response(
            tokens,
            success_message="Login successful"
        )

    except ValueError:
        raise HttpError(
            status_code=401,
            message="Invalid email or password",
            error_code="INVALID_CREDENTIALS"
        )
    except Exception as e:
        raise HttpError(
            status_code=500,
            message="An unexpected error occurred during login",
            error_code="LOGIN_ERROR"
        )


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    **register_docs
)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_public_db)
) -> RegisterResponse:
    """
    Create a new user account with secure password hashing.
    """
    auth_service = AuthService(db)

    try:
        user = await auth_service.register(payload)
        return send_custom_response(
            user,
            success_message="User registered successfully"
        )

    except ValueError as e:
        raise HttpError(
            status_code=400,
            message=str(e),
            error_code="REGISTRATION_ERROR"
        )
    except Exception as e:
        raise HttpError(
            status_code=500,
            message="An unexpected error occurred during registration",
            error_code="REGISTRATION_ERROR"
        )