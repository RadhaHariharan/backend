from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from utils.date_time import utc_now

class AuditMixin:
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("public.users.id"),
        nullable=False,
    )

    updated_by = Column(
        UUID(as_uuid=True),
        ForeignKey("public.users.id"),
        nullable=False,
    )
