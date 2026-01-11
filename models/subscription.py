from sqlalchemy import Column, String, Numeric, Boolean, TIMESTAMP, Text, Integer, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from core.database import Base


class PlanFeature(Base):
    """
    Maps which features are included in which plans.
    Allows override of default limits per plan.
    """
    __tablename__ = "plan_features"
    __table_args__ = (
        {"schema": "public", "unique": ("plan_id", "feature_id")}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    plan_id = Column(UUID(as_uuid=True), ForeignKey("public.plans.id"), nullable=False)
    feature_id = Column(UUID(as_uuid=True), ForeignKey("public.features.id"), nullable=False)
    
    # Override defaults for this plan
    limit_override = Column(Integer)  # NULL = use feature's default_limit
    price_override = Column(Numeric(10, 2))  # NULL = use feature's standalone_price
    
    included_by_default = Column(Boolean, default=True)  # Automatically included?
    
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Subscription(Base):
    """
    Organization subscription to a base plan.
    Stored in public schema (not tenant-specific).
    """
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint("status IN ('trialing', 'active', 'past_due', 'cancelled', 'incomplete')"),
        {"schema": "public"}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Organization & Plan
    org_id = Column(UUID(as_uuid=True), nullable=False)  # FK to organizations.id
    plan_id = Column(UUID(as_uuid=True), ForeignKey("public.plans.id"), nullable=False)
    
    # Subscription Status
    status = Column(String(20), default='trialing')  # 'trialing', 'active', 'past_due', 'cancelled', 'incomplete'
    
    # Billing Periods
    current_period_start = Column(TIMESTAMP(timezone=True), nullable=False)
    current_period_end = Column(TIMESTAMP(timezone=True), nullable=False)
    trial_end = Column(TIMESTAMP(timezone=True))
    
    # Pricing Breakdown
    base_amount = Column(Numeric(10, 2), nullable=False)  # Plan base price
    setup_fee = Column(Numeric(10, 2), default=0)  # Setup fee
    discount_amount = Column(Numeric(10, 2), default=0)  # Total discounts applied
    tax_amount = Column(Numeric(10, 2), default=0)  # Tax
    total_amount = Column(Numeric(10, 2), nullable=False)  # Final amount
    
    # Stripe Integration
    stripe_subscription_id = Column(String(255), unique=True, nullable=True)
    stripe_customer_id = Column(String(255), nullable=True)
    
    # Configuration
    auto_renew = Column(Boolean, default=True)
    send_invoices = Column(Boolean, default=True)
    metadata = Column(JSONB, default={})  # Custom data, notes, etc.
    
    # Dates
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    cancelled_at = Column(TIMESTAMP(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "id": str(self.id),
            "org_id": str(self.org_id),
            "plan_id": str(self.plan_id),
            "status": self.status,
            "current_period_start": self.current_period_start.isoformat(),
            "current_period_end": self.current_period_end.isoformat(),
            "trial_end": self.trial_end.isoformat() if self.trial_end else None,
            "base_amount": float(self.base_amount),
            "setup_fee": float(self.setup_fee),
            "discount_amount": float(self.discount_amount),
            "tax_amount": float(self.tax_amount),
            "total_amount": float(self.total_amount),
            "created_at": self.created_at.isoformat(),
            "auto_renew": self.auto_renew
        }


class SubscriptionAddon(Base):
    """
    À la carte features added on top of base plan.
    Allows custom pricing and limits per organization.
    """
    __tablename__ = "subscription_addons"
    __table_args__ = (
        {"schema": "public", "unique": ("subscription_id", "feature_id")}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("public.subscriptions.id"), nullable=False)
    feature_id = Column(UUID(as_uuid=True), ForeignKey("public.features.id"), nullable=False)
    
    # Custom Pricing for this Addon
    unit_price = Column(Numeric(10, 2), nullable=False)  # Price at time of purchase
    setup_fee = Column(Numeric(10, 2), default=0)
    discount_amount = Column(Numeric(10, 2), default=0)
    tax_amount = Column(Numeric(10, 2), default=0)
    final_price = Column(Numeric(10, 2), nullable=False)  # unit_price - discount + tax
    
    # Custom Limits
    limit_override = Column(Integer)  # NULL = use feature's default_limit
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Stripe
    stripe_item_id = Column(String(255), unique=True, nullable=True)
    
    # Dates
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    removed_at = Column(TIMESTAMP(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "id": str(self.id),
            "feature_id": str(self.feature_id),
            "unit_price": float(self.unit_price),
            "discount_amount": float(self.discount_amount),
            "final_price": float(self.final_price),
            "limit": self.limit_override,
            "is_active": self.is_active
        }


class Discount(Base):
    """
    Discount codes and rules.
    Flexible application to plans, features, or both.
    """
    __tablename__ = "discounts"
    __table_args__ = (
        CheckConstraint("discount_type IN ('percentage', 'fixed_amount')"),
        CheckConstraint("applies_to IN ('plan', 'feature', 'both')"),
        {"schema": "public"}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    code = Column(String(50), unique=True, nullable=False)  # 'SUMMER2024'
    name = Column(String(100))  # Display name
    description = Column(Text)
    
    # Discount Type
    discount_type = Column(String(20), nullable=False)  # 'percentage' or 'fixed_amount'
    discount_value = Column(Numeric(10, 2), nullable=False)  # 20 (for 20%) or 10.00 (for $10)
    
    # Applicability
    applies_to = Column(String(20), nullable=False)  # 'plan', 'feature', 'both'
    plan_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)  # NULL = all plans
    feature_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)  # NULL = all features
    
    # Validity
    valid_from = Column(TIMESTAMP(timezone=True), nullable=False)
    valid_until = Column(TIMESTAMP(timezone=True), nullable=True)
    max_uses = Column(Integer, nullable=True)  # NULL = unlimited
    current_uses = Column(Integer, default=0)
    max_uses_per_customer = Column(Integer, default=1)
    
    # Constraints
    min_purchase_amount = Column(Numeric(10, 2), nullable=True)
    max_discount_amount = Column(Numeric(10, 2), nullable=True)  # Cap on discount amount
    
    # Status
    is_active = Column(Boolean, default=True)
    metadata = Column(JSONB, default={})
    
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": str(self.id),
            "code": self.code,
            "name": self.name,
            "discount_type": self.discount_type,
            "discount_value": float(self.discount_value),
            "applies_to": self.applies_to,
            "is_active": self.is_active
        }


class SubscriptionDiscount(Base):
    """
    Tracks which discounts are applied to which subscriptions.
    Snapshot of discount at time of application.
    """
    __tablename__ = "subscription_discounts"
    __table_args__ = ({"schema": "public"},)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("public.subscriptions.id"), nullable=False)
    discount_id = Column(UUID(as_uuid=True), ForeignKey("public.discounts.id"), nullable=False)
    
    # Snapshot of discount details
    discount_type = Column(String(20), nullable=False)
    discount_value = Column(Numeric(10, 2), nullable=False)
    amount_saved = Column(Numeric(10, 2), nullable=False)
    
    # Target
    applied_to = Column(String(20), nullable=False)  # 'plan' or 'addon'
    addon_id = Column(UUID(as_uuid=True), nullable=True)  # FK to subscription_addons.id if addon
    
    applied_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": str(self.id),
            "discount_id": str(self.discount_id),
            "discount_type": self.discount_type,
            "amount_saved": float(self.amount_saved),
            "applied_to": self.applied_to
        }


class FeatureUsage(Base):
    """
    Tracks usage of quota-based features.
    One record per feature per billing period per organization.
    """
    __tablename__ = "feature_usage"
    __table_args__ = (
        {"schema": "public", "unique": ("org_id", "feature_id", "period_start")}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    org_id = Column(UUID(as_uuid=True), nullable=False)  # FK to organizations.id
    feature_id = Column(UUID(as_uuid=True), ForeignKey("public.features.id"), nullable=False)
    
    # Usage Tracking
    usage_count = Column(Integer, default=0)
    limit_amount = Column(Integer, nullable=True)  # NULL = unlimited
    
    # Period
    period_start = Column(TIMESTAMP(timezone=True), nullable=False)
    period_end = Column(TIMESTAMP(timezone=True), nullable=False)
    
    # Configuration
    reset_warning_sent = Column(Boolean, default=False)
    exceeded_notification_sent = Column(Boolean, default=False)
    metadata = Column(JSONB, default={})  # {last_reset, overage_allowed, etc}
    
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": str(self.id),
            "feature_id": str(self.feature_id),
            "usage_count": self.usage_count,
            "limit": self.limit_amount,
            "remaining": self.limit_amount - self.usage_count if self.limit_amount else None,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat()
        }
