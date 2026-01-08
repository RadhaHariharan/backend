from sqlalchemy.orm import Session

from repositories.user_repo import UserRepository
from core.security import verify_password, create_access_token, create_refresh_token


class AuthService:
    def __init__(self, db: Session):
        self.user_repo = UserRepository(db)

    def login(self, email: str, password: str):
        user = self.user_repo.get_by_email(email)

        if not user or not verify_password(password, user.hashed_password):
            raise ValueError("Invalid credentials")

        return {
            "access_token": create_access_token({
                "sub": user.id,
                "org": user.organization_id
            }),
            "refresh_token": create_refresh_token(user.id),
            "token_type": "bearer"
        }
