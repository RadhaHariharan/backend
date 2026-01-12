from passlib.context import CryptContext
import uuid
from jose import jwt
from datetime import timedelta
from typing import Optional
from core.config import settings
from utils.date_time import utc_now


#: Passlib cryptographic context for password hashing
#: Uses bcrypt as the hashing algorithm
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


def create_access_token(data: dict, org_id: Optional[str] = None) -> str:
    """
    Create a JWT access token.

    The access token is short-lived and intended for authenticating
    API requests. UUID values in the payload are automatically
    converted to strings to ensure JSON serialization compatibility.

    Args:
        data (dict):
            Token payload. Must include the `sub` claim representing
            the user identifier. Values may include UUID objects.
        org_id (Optional[str]):
            Optional organization UUID to scope the token.
            If provided, it will be embedded as `orgId`.

    Returns:
        str:
            Encoded JWT access token.

    Notes:
        - Token expiration is fixed at 15 minutes.
        - Uses the secret key and algorithm defined in application settings.
        - All UUID values are converted to strings before encoding.
    """
    payload = data.copy()

    # Convert UUID values to strings for JSON serialization
    for k, v in payload.items():
        if isinstance(v, uuid.UUID):
            payload[k] = str(v)

    if org_id:
        payload["orgId"] = str(org_id)

    payload["exp"] = utc_now() + timedelta(minutes=15)

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(
    user_id: uuid.UUID,
    org_id: Optional[str] = None
) -> str:
    """
    Create a JWT refresh token.

    Refresh tokens are long-lived and used to obtain new access tokens
    without requiring the user to re-authenticate.

    Args:
        user_id (uuid.UUID):
            Unique identifier of the user.
        org_id (Optional[str]):
            Optional organization UUID to scope the token.
            If provided, it will be embedded as `orgId`.

    Returns:
        str:
            Encoded JWT refresh token.

    Notes:
        - Token expiration is fixed at 30 days.
        - The `sub` claim always contains the user ID as a string.
        - Uses the same signing key and algorithm as access tokens.
    """
    payload = {
        "sub": str(user_id),
        "exp": utc_now() + timedelta(days=30),
    }

    if org_id:
        payload["orgId"] = str(org_id)

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using bcrypt.

    This function uses Passlib's CryptContext to generate a secure,
    salted bcrypt hash suitable for persistent storage.

    Args:
        password (str):
            Plaintext password provided by the user.

    Returns:
        str:
            Bcrypt-hashed password.

    Security:
        - Automatically handles salt generation.
        - Resistant to rainbow table and brute-force attacks.
    """
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plaintext password against a stored bcrypt hash.

    Args:
        plain (str):
            Plaintext password provided by the user.
        hashed (str):
            Stored bcrypt hash retrieved from the database.

    Returns:
        bool:
            True if the password matches the hash, False otherwise.

    Notes:
        - Uses constant-time comparison internally.
        - Safe against timing attacks.
    """
    return pwd_context.verify(plain, hashed)
