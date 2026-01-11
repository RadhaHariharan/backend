import uuid
from sqlalchemy import Column, DateTime, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base
from utils.date_time import utc_now


class UserOrgRole(Base):
    """User role assignments within an organization - stored in tenant schema"""
    __tablename__ = "user_org_roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    role_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    assigned_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role"),
        Index("ix_user_org_roles_role_id", "role_id"),
    )

    def __repr__(self) -> str:
        return f"<UserOrgRole user={self.user_id} role={self.role_id}>"
