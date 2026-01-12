from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

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
    summary="User Login",
    description="""
    Authenticate a user with email and password credentials.
    
    Process:
    - Validates email format and password
    - Verifies credentials against database
    - Generates JWT access and refresh tokens
    - Returns tokens with user information
    
    Response includes:
    - `access_token`: JWT token for API authentication
    - `refresh_token`: Token to obtain new access tokens
    - `token_type`: Always "bearer"
    - `expires_in`: Token expiration time in seconds
    """,
    responses={
        200: {
            "description": "Login successful",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Login successful",
                        "data": {
                            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                            "token_type": "bearer",
                            "expires_in": 3600
                        }
                    }
                }
            }
        },
        401: {
            "description": "Invalid credentials",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "message": "Invalid email or password",
                        "error_code": "INVALID_CREDENTIALS"
                    }
                }
            }
        },
        500: {
            "description": "Internal server error"
        }
    }
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
    summary="User Registration",
    description="""
    Create a new user account in the system.
    
    Process:
    - Validates email uniqueness
    - Validates password strength
    - Securely hashes password using bcrypt
    - Creates user record in database
    - Returns created user details
    
    Password Requirements:
    - Minimum 8 characters
    - Must contain uppercase and lowercase letters
    - Must contain at least one number
    - Must contain at least one special character
    """,
    responses={
        201: {
            "description": "User registered successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "User registered successfully",
                        "data": {
                            "id": "123e4567-e89b-12d3-a456-426614174000",
                        }
                    }
                }
            }
        },
        400: {
            "description": "Email already registered or validation error",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "message": "Email already registered",
                        "error_code": "EMAIL_ALREADY_REGISTERED"
                    }
                }
            }
        },
        422: {
            "description": "Validation error - invalid input data"
        },
        500: {
            "description": "Internal server error"
        }
    }
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
        user = await auth_service.register(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            password=payload.password
        )
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