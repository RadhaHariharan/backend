import uuid
from sqlalchemy import Column, String, DateTime, Index, Text
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from core.database import Base
from utils.date_time import utc_now


class Role(Base):
    """Organization-specific roles - stored in tenant schema"""
    __tablename__ = "roles"
    # NO __table_args__ with schema - uses tenant schema from search_path

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Permissions as array of strings
    permissions = Column(ARRAY(String), nullable=False, default=list)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_roles_name", "name"),
    )

    def __repr__(self) -> str:
        return f"<Role id={self.id} name={self.name}>"
