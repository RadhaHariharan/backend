login_docs = dict(
    summary="User Login",
    description="""
    Authenticate a user with email and password credentials.
    
    Process:
    - Validates email format and password
    - Verifies credentials against database
    - Generates JWT access and refresh tokens
    - Returns tokens with user information
    
    Response includes:
    - `access_token`: JWT token for API authentication
    - `refresh_token`: Token to obtain new access tokens
    - `token_type`: Always "bearer"
    - `expires_in`: Token expiration time in seconds
    """,
    responses={
        200: {
            "description": "Login successful",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Login successful",
                        "data": {
                            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                            "token_type": "bearer",
                            "expires_in": 3600
                        }
                    }
                }
            }
        },
        401: {
            "description": "Invalid credentials",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "message": "Invalid email or password",
                        "error_code": "INVALID_CREDENTIALS"
                    }
                }
            }
        },
        500: {
            "description": "Internal server error"
        }
    }
)

register_docs = dict(
    summary="User Registration",
    description="""
    Create a new user account in the system.
    
    Process:
    - Validates email uniqueness
    - Validates password strength
    - Securely hashes password using bcrypt
    - Creates user record in database
    - Returns created user details
    
    Password Requirements:
    - Minimum 8 characters
    - Must contain uppercase and lowercase letters
    - Must contain at least one number
    - Must contain at least one special character
    """,
    responses={
        201: {
            "description": "User registered successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "User registered successfully",
                        "data": {
                            "id": "123e4567-e89b-12d3-a456-426614174000",
                        }
                    }
                }
            }
        },
        400: {
            "description": "Email already registered or validation error",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "message": "Email already registered",
                        "error_code": "EMAIL_ALREADY_REGISTERED"
                    }
                }
            }
        },
        422: {
            "description": "Validation error - invalid input data"
        },
        500: {
            "description": "Internal server error"
        }
    }
)
