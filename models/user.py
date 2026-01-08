from sqlalchemy import (
    Column,
    Integer,
    String,
    SmallInteger,
    DateTime,
    Index
)
from core.database import Base
from utils.date_time import utc_now

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    # Identity
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    # Status: 0 = inactive, 1 = active
    status = Column(SmallInteger, default=1, nullable=False)

    # Audit timestamps
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False
    )

    __table_args__ = (
        Index("ix_users_email_status", "email", "status"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} status={self.status}>"
    
    @property
    def full_name(self) -> str:
        """Get user's full name"""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_active(self) -> bool:
        """Check if user is active"""
        return self.status == 1