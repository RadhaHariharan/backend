from sqlalchemy import Column, String, Numeric, Boolean, TIMESTAMP, Text, Integer, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from datetime import datetime, timezone

from core.database import Base


class Feature(Base):
    """
    Represents a billable feature that can be included in plans or purchased à la carte.
    Stored in public schema (shared across all orgs).
    
    Feature Types:
    - 'boolean': Either enabled or disabled (e.g., Advanced Analytics, White Label)
    - 'quota': Limited usage per period (e.g., API calls, integrations)
    - 'unlimited': No usage limits (e.g., Priority Support)
    """
    __tablename__ = "features"
    __table_args__ = (
        CheckConstraint("feature_type IN ('boolean', 'quota', 'unlimited')"),
        {"schema": "public"}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Metadata
    name = Column(String(100), nullable=False)  # 'Advanced Analytics'
    slug = Column(String(100), unique=True, nullable=False)  # 'advanced_analytics'
    description = Column(Text)
    category = Column(String(50))  # 'analytics', 'api', 'support', 'integrations'
    
    # Type & Limits
    feature_type = Column(String(20), nullable=False)  # 'boolean', 'quota', 'unlimited'
    default_limit = Column(Integer)  # NULL = unlimited, else specific number (for quota features)
    
    # Pricing
    standalone_price = Column(Numeric(10, 2))  # Price if purchased separately
    setup_fee = Column(Numeric(10, 2), default=0)
    trial_period_days = Column(Integer, default=0)  # Trial days for this feature
    
    # Configuration
    metadata = Column(JSONB, default={})  # {stripe_price_id, unit: 'api_calls', etc}
    customizable = Column(Boolean, default=True)  # Can price/limit be customized per org?
    
    # Status
    is_active = Column(Boolean, default=True)
    is_beta = Column(Boolean, default=False)
    display_order = Column(Integer, default=0)
    
    # Dates
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "category": self.category,
            "feature_type": self.feature_type,
            "default_limit": self.default_limit,
            "standalone_price": float(self.standalone_price) if self.standalone_price else None,
            "is_active": self.is_active,
            "is_beta": self.is_beta,
            "customizable": self.customizable
        }
