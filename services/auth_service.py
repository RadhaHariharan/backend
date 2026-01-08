from sqlalchemy.ext.asyncio import AsyncSession
from repositories.user_repo import UserRepository
from core.security import verify_password, create_access_token, create_refresh_token, hash_password
from models.user import User

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

    async def register(self, first_name: str, last_name: str, email: str, password: str):
        """Register a new user"""
        # Check if user already exists
        existing_user = await self.user_repo.get_by_email(email)
        if existing_user:
            raise ValueError("Email already registered")
        
        # Hash password
        password_hash = hash_password(password)
        
        # Create new user
        new_user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password_hash=password_hash,
            status=1  # Active by default
        )
        
        # Save to database
        created_user = await self.user_repo.create(new_user)
        
        return {
            "id": str(created_user.id),
            "first_name": created_user.first_name,
            "last_name": created_user.last_name,
            "email": created_user.email
        }