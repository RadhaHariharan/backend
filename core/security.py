from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from core.config import settings
from utils.date_time import utc_now

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain, hashed):
    truncated_plain = plain[:72]
    return pwd_context.verify(truncated_plain, hashed)

def create_access_token(data: dict):
    payload = data.copy()
    payload["exp"] = utc_now + timedelta(minutes=15)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token(user_id: int):
    payload = {
        "sub": user_id,
        "exp": utc_now + timedelta(days=30)
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def hash_password(password: str) -> str:
    truncated_password = password[:72]
    return pwd_context.hash(truncated_password)
