import uuid
from sqlalchemy import Column, String, SmallInteger, DateTime, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base
from utils.date_time import utc_now


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Organization info
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Owner
    owner_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Status: 0 = inactive, 1 = active, 2 = suspended
    status = Column(SmallInteger, default=1, nullable=False)
    
    # Audit
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_organizations_owner_id", "owner_id"),
        Index("ix_organizations_slug_status", "slug", "status"),
        {"schema": "public"}
    )

    def __repr__(self) -> str:
        return f"<Organization id={self.id} name={self.name}>"
    
    @property
    def is_active(self) -> bool:
        return self.status == 1
    
    @property
    def schema_name(self) -> str:
        """Schema name is the organization UUID as string with underscores"""
        return str(self.id).replace('-', '_')
