from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import get_db
from schemas.auth import LoginRequest, TokenResponse
from services.auth_service import AuthService
from utils.response import send_custom_response, HttpError

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login endpoint:
    - verifies email & password
    - returns access + refresh tokens
    - uses centralized response structure
    """
    auth_service = AuthService(db)

    try:
        tokens = auth_service.login(
            email=payload.email,
            password=payload.password
        )
        # Success response
        return send_custom_response(tokens, success_message="Login successful")
    except ValueError:
        # Invalid credentials
        raise HttpError(401, "Invalid email or password", "INVALID_CREDENTIALS")
    except Exception as e:
        # Any other unexpected error
        raise HttpError(500, "Internal Server Error", str(e))
