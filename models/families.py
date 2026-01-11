import uuid
from sqlalchemy import Column, ForeignKey, String, SmallInteger, DateTime, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base
from core.database_mixins import AuditMixin
from models.user import User
from utils.date_time import utc_now


class Family(Base, AuditMixin):
    __tablename__ = "families"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Family info
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Owner
    owner_id = Column(UUID(as_uuid=True), ForeignKey(User.__table__.c.id), nullable=False, index=True)
    
    # Status: 0 = inactive, 1 = active, 2 = suspended
    status = Column(SmallInteger, default=1, nullable=False)

    __table_args__ = (
        Index("ix_organizations_owner_id", "owner_id"),
        Index("ix_organizations_slug_status", "slug", "status"),
        {"schema": "public"}
    )

    def __repr__(self) -> str:
        return f"<Family id={self.id} name={self.name}>"
    
    @property
    def is_active(self) -> bool:
        return self.status == 1
    
    @property
    def schema_name(self) -> str:
        """Schema name is the organization UUID as string with underscores"""
        return str(self.id).replace('-', '_')
