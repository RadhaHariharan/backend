import uuid
from jose import jwt
from datetime import timedelta
from typing import Optional
from core.config import settings
from utils.date_time import utc_now
import bcrypt


def create_access_token(data: dict, org_id: Optional[str] = None) -> str:
    """
    Generate a short-lived JWT access token for authentication.

    The access token is used to authenticate API requests. Any UUID values
    in the payload are automatically converted to strings for JSON serialization.

    Args:
        data (dict): 
            Dictionary containing token claims. Must include a `sub` claim
            representing the user identifier. Can include UUID values.
        org_id (Optional[str]): 
            Optional organization UUID to scope the token. If provided, 
            it will be added to the payload as `orgId`.

    Returns:
        str: Encoded JWT access token.

    Notes:
        - Token expiration is set to 15 minutes from the time of creation.
        - Uses the secret key and algorithm defined in application settings.
        - UUID values in the payload are converted to strings for JSON compatibility.
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


def create_refresh_token(user_id: uuid.UUID, org_id: Optional[str] = None) -> str:
    """
    Generate a long-lived JWT refresh token.

    Refresh tokens are used to obtain new access tokens without requiring
    the user to re-authenticate. The `sub` claim always contains the
    user ID as a string.

    Args:
        user_id (uuid.UUID): Unique identifier of the user.
        org_id (Optional[str]): Optional organization UUID to scope the token.
            If provided, it will be added to the payload as `orgId`.

    Returns:
        str: Encoded JWT refresh token.

    Notes:
        - Token expiration is set to 30 days from the time of creation.
        - Uses the same secret key and algorithm as access tokens.
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

    This function generates a secure, salted bcrypt hash suitable for storage.
    The password is first encoded to UTF-8 bytes before hashing.

    Args:
        password (str): Plaintext password provided by the user.

    Returns:
        str: Bcrypt-hashed password as a UTF-8 string.

    Notes:
        - Automatically generates a salt using bcrypt.
        - Safe for persistent storage.
        - Passwords longer than 72 bytes are truncated internally by bcrypt.
    """
    salt = bcrypt.gensalt()
    hashedBytes = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashedBytes.decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plaintext password against a stored bcrypt hash.

    Args:
        plain (str): Plaintext password provided by the user.
        hashed (str): Stored bcrypt hash retrieved from the database.

    Returns:
        bool: True if the password matches the hash, False otherwise.

    Notes:
        - Both the plaintext and hash are encoded to UTF-8 bytes for verification.
        - Safe against timing attacks.
        - Passwords longer than 72 bytes are truncated internally by bcrypt.
    """
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
