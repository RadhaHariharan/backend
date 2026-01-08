import uuid
from jose import jwt
from datetime import timedelta
from core.config import settings
from utils.date_time import utc_now
import bcrypt

def create_access_token(data: dict):
    payload = data.copy()
    for k, v in payload.items():
        if isinstance(v, uuid.UUID):
            payload[k] = str(v)
    payload["exp"] = utc_now() + timedelta(minutes=15)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def create_refresh_token(user_id: uuid.UUID):
    payload = {
        "sub": str(user_id),
        "exp": utc_now() + timedelta(days=30)
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashedBytes = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashedBytes.decode('utf-8')

def verify_password(plain, hashed):
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
