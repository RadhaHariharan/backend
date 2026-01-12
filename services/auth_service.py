from sqlalchemy.ext.asyncio import AsyncSession
from repositories.user_repo import UserRepository
from core.security import verify_password, create_access_token, create_refresh_token, hash_password
from models.user import User
from schemas.auth import RegisterRequest

class AuthService:
    def __init__(self, db: AsyncSession):
        self.user_repo = UserRepository(db)

    async def login(self, email: str, password: str):
        user = await self.user_repo.get_by_email(email)  # ← Now with await

        if not user or not verify_password(password, user.password):
            raise ValueError("Invalid credentials")

        return {
            "access_token": create_access_token({
                "sub": user.id,
                "email": user.email
            }),
            "refresh_token": create_refresh_token(user.id),
            "token_type": "bearer"
        }

    async def register(self, payload: RegisterRequest):
        """Register a new user using the full RegisterRequest schema"""
        # Check if user already exists
        existing_user = await self.user_repo.get_by_email(payload.email)
        if existing_user:
            raise ValueError("Email already registered")

        # Convert payload to dict and remove password
        user_data = payload.model_dump(exclude={"password"})

        # Hash password separately
        user_data["password"] = hash_password(payload.password)
        user_data["status"] = 1  # default active status

        # Create new User object
        new_user = User(**user_data)

        # Save to database
        created_user = await self.user_repo.create(new_user)

        # Return the created user info (omit password)
        return {"id": str(created_user.id)}