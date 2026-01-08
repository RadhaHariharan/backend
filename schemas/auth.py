from pydantic import BaseModel, EmailStr, Field

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., max_length=72, description="Password must be 72 characters or less")

class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str = Field(..., max_length=72, description="Password must be 72 characters or less")

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: str
    
    class Config:
        from_attributes = True
