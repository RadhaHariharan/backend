import uuid
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Index
)
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base
from utils.date_time import utc_now


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_mobile", "country_code", "mobile_number"),
        {"schema": "public"},
    )

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identity
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)

    # Contact
    country_code = Column(String(5), nullable=False)       # e.g. +91
    mobile_number = Column(String(15), nullable=False)     # stored as string
    email = Column(String(255), unique=True, nullable=False)

    # Address
    address_line_1 = Column(String(255), nullable=False)
    address_line_2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    country = Column(String(100), nullable=False)
    zipcode = Column(String(20), nullable=False)

    # Security
    password_hash = Column(String(255), nullable=False)

    # Audit timestamps (UTC)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
