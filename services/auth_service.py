from sqlalchemy.ext.asyncio import AsyncSession
from repositories.user_repo import UserRepository
from core.security import verify_password, create_access_token, create_refresh_token


class AuthService:
    def __init__(self, db: AsyncSession):
        self.user_repo = UserRepository(db)

    async def login(self, email: str, password: str):
        user = await self.user_repo.get_by_email(email)  # ← Now with await

        if not user or not verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials")

        return {
            "access_token": create_access_token({
                "sub": user.id,
                "email": user.email
            }),
            "refresh_token": create_refresh_token(user.id),
            "token_type": "bearer"
        }