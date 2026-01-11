import uuid
from sqlalchemy import Column, SmallInteger, DateTime, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base
from utils.date_time import utc_now


class OrgUser(Base):
    """
    Users within an organization - stored in TENANT schema
    This tracks organization membership and roles within that specific org
    """
    __tablename__ = "org_users"
    # NO __table_args__ with schema - uses tenant schema from search_path

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Reference to user in public.users
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # User's email (denormalized for easier queries within org)
    email = Column(String(255), nullable=False, index=True)
    
    # User's name (denormalized)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    
    # Role in this org: 0 = member, 1 = admin, 2 = owner
    role_type = Column(SmallInteger, default=0, nullable=False)
    
    # Status: 0 = inactive, 1 = active, 2 = pending invitation
    status = Column(SmallInteger, default=1, nullable=False)
    
    # Timestamps
    joined_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_org_user_id"),
        Index("ix_org_users_email", "email"),
        Index("ix_org_users_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<OrgUser user_id={self.user_id} email={self.email} role={self.role_type}>"
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_active(self) -> bool:
        return self.status == 1
    
    @property
    def is_owner(self) -> bool:
        return self.role_type == 2
    
    @property
    def is_admin(self) -> bool:
        return self.role_type >= 1  # Admin or Owner
