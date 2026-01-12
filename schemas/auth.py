from pydantic import BaseModel, ConfigDict, Field, EmailStr
from typing_extensions import Annotated
from typing import Optional

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., max_length=72, description="Password must be 72 characters or less")

from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing_extensions import Annotated
from typing import Optional


class RegisterRequest(BaseModel):
    """
    Schema for user registration.

    Uses `typing.Annotated` for modern, type-safe field metadata.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "country_code": 101,
                "mobile_number": "9876543210",
                "address_line_1": "221B Baker Street",
                "address_line_2": "Near Central Park",
                "city": 132011,
                "state": 4035,
                "country": 101,
                "zipcode": "632602",
                "password": "Admin@123"
            }
        }
    )

    # Identity
    first_name: Annotated[
        str,
        Field(max_length=100, description="User first name")
    ]
    last_name: Annotated[
        str,
        Field(max_length=100, description="User last name")
    ]

    # Contact
    email: Annotated[
        EmailStr,
        Field(description="Unique email address")
    ]
    country_code: Annotated[
        int,
        Field(description="Country calling code (default: 1)")
    ]
    mobile_number: Annotated[
        str,
        Field(max_length=15, description="User mobile number")
    ]

    # Address
    address_line_1: Annotated[
        str,
        Field(max_length=255, description="Primary address line")
    ]
    address_line_2: Annotated[
        Optional[str],
        Field(default=None, max_length=255, description="Secondary address line")
    ]
    city: Annotated[
        int,
        Field(description="City identifier")
    ]
    state: Annotated[
        int,
        Field(description="State identifier")
    ]
    country: Annotated[
        int,
        Field(description="Country identifier")
    ]
    zipcode: Annotated[
        str,
        Field(
            max_length=20,
            description="Postal / ZIP code"
        )
    ]

    # Security
    password: Annotated[
        str,
        Field(
            min_length=8,
            max_length=72,
            description="Password (bcrypt supports max 72 characters)"
        )
    ]

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RegisterResponse(BaseModel):
    id: str
    
    class Config:
        from_attributes = True
