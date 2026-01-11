from sqlalchemy import Column, String, Numeric, Boolean, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Plan(Base):
    """
    Represents a subscription plan tier.
    Stored in tenant schema.
    
    Example:
        - Beginner: $9.99/month
        - Pro: $29.99/month
        - Expert: $99.99/month
    """
    __tablename__ = "plans"
    __table_args__ = ({"schema": "public"},)  # Shared across all orgs initially, can be made per-org

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)  # 'Beginner', 'Pro', 'Expert'
    slug = Column(String(100), unique=True, nullable=False)  # 'beginner', 'pro', 'expert'
    description = Column(Text)
    
    # Pricing
    base_price = Column(Numeric(10, 2), nullable=False)  # Monthly base price
    setup_fee = Column(Numeric(10, 2), default=0)  # One-time setup cost
    billing_interval = Column(String(20), default='monthly')  # 'monthly', 'yearly', 'custom'
    
    # Features
    max_features = Column(String(100))  # JSON string of max counts: {"users": 10, "projects": 5}
    metadata = Column(JSONB, default={})  # Stripe price IDs, etc.
    
    # Status
    is_active = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)
    display_order = Column(Numeric, default=0)
    
    # Dates
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "base_price": float(self.base_price),
            "setup_fee": float(self.setup_fee),
            "billing_interval": self.billing_interval,
            "is_active": self.is_active,
            "is_featured": self.is_featured,
            "metadata": self.metadata
        }
