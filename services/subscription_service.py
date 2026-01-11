"""
Advanced Subscription Management Service
Handles all subscription operations: creation, modification, cancellation
Includes pricing calculations, discount application, and usage tracking
"""

from decimal import Decimal
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from uuid import UUID
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, and_, or_
from sqlalchemy.orm import selectinload

from models.subscription import (
    Subscription, SubscriptionAddon, Plan, Feature, PlanFeature,
    Discount, SubscriptionDiscount, FeatureUsage
)
from utils.response import HttpError


class SubscriptionService:
    """
    Comprehensive subscription management service.
    Handles creation, updates, cancellations, and complex pricing scenarios.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db

    # ===================== SUBSCRIPTION CREATION =====================

    async def create_subscription(
        self,
        org_id: UUID,
        plan_slug: str,
        trial_days: int = 0,
        metadata: Optional[Dict] = None,
        stripe_customer_id: Optional[str] = None
    ) -> Subscription:
        """
        Create a new subscription for an organization.
        
        Args:
            org_id: Organization ID
            plan_slug: Plan slug (e.g., 'beginner', 'pro')
            trial_days: Number of trial days
            metadata: Additional metadata
            stripe_customer_id: (DEPRECATED) Will be used in payment processing - TODO: Implement Stripe integration
            
        Returns:
            Created Subscription object
            
        Raises:
            HttpError: If plan not found or subscription already exists
        """
        
        # Check if subscription already exists
        existing = await self.db.execute(
            select(Subscription).where(
                and_(
                    Subscription.org_id == org_id,
                    Subscription.status.in_(['active', 'trialing'])
                )
            )
        )
        
        if existing.scalar_one_or_none():
            raise HttpError(400, "Organization already has active subscription", "SUBSCRIPTION_EXISTS")
        
        # Get plan
        plan_result = await self.db.execute(
            select(Plan).where(
                and_(Plan.slug == plan_slug, Plan.is_active == True)
            )
        )
        plan = plan_result.scalar_one_or_none()
        
        if not plan:
            raise HttpError(404, f"Plan '{plan_slug}' not found", "PLAN_NOT_FOUND")
        
        # Calculate periods
        now = datetime.now(timezone.utc)
        period_start = now
        period_end = now + timedelta(days=30)
        trial_end = now + timedelta(days=trial_days) if trial_days > 0 else None
        
        # Calculate total amount
        base_amount = plan.base_price
        setup_fee = plan.setup_fee or Decimal('0.00')
        total_amount = base_amount + setup_fee
        
        # Create subscription
        subscription = Subscription(
            id=uuid.uuid4(),
            org_id=org_id,
            plan_id=plan.id,
            status='trialing' if trial_days > 0 else 'active',
            current_period_start=period_start,
            current_period_end=period_end,
            trial_end=trial_end,
            base_amount=base_amount,
            setup_fee=setup_fee,
            discount_amount=Decimal('0.00'),
            tax_amount=Decimal('0.00'),
            total_amount=total_amount,
            stripe_customer_id=stripe_customer_id,
            auto_renew=True,
            metadata=metadata or {}
        )
        
        self.db.add(subscription)
        await self.db.commit()
        await self.db.refresh(subscription)
        
        # Initialize usage tracking for quota-based features
        await self._initialize_usage_tracking(org_id, subscription.id)
        
        return subscription

    # ===================== ADDON MANAGEMENT =====================

    async def add_addon(
        self,
        subscription_id: UUID,
        feature_slug: str,
        custom_limit: Optional[int] = None,
        custom_price: Optional[Decimal] = None
    ) -> SubscriptionAddon:
        """
        Add a feature addon to an existing subscription.
        Allows complete customization of price and limits.
        
        Args:
            subscription_id: Subscription ID
            feature_slug: Feature slug
            custom_limit: Override default limit
            custom_price: Override standalone price
            
        Returns:
            Created SubscriptionAddon
        """
        
        # Get subscription
        sub_result = await self.db.execute(
            select(Subscription).where(Subscription.id == subscription_id)
        )
        subscription = sub_result.scalar_one_or_none()
        
        if not subscription:
            raise HttpError(404, "Subscription not found", "SUBSCRIPTION_NOT_FOUND")
        
        # Get feature
        feature_result = await self.db.execute(
            select(Feature).where(
                and_(Feature.slug == feature_slug, Feature.is_active == True)
            )
        )
        feature = feature_result.scalar_one_or_none()
        
        if not feature:
            raise HttpError(404, f"Feature '{feature_slug}' not found", "FEATURE_NOT_FOUND")
        
        # Check if already exists
        existing = await self.db.execute(
            select(SubscriptionAddon).where(
                and_(
                    SubscriptionAddon.subscription_id == subscription_id,
                    SubscriptionAddon.feature_id == feature.id,
                    SubscriptionAddon.is_active == True
                )
            )
        )
        
        if existing.scalar_one_or_none():
            raise HttpError(400, "Addon already exists for this subscription", "ADDON_EXISTS")
        
        # Determine pricing
        price = custom_price or feature.standalone_price
        if not price:
            raise HttpError(400, "Feature has no price", "NO_PRICE")
        
        # Create addon
        addon = SubscriptionAddon(
            id=uuid.uuid4(),
            subscription_id=subscription_id,
            feature_id=feature.id,
            unit_price=price,
            setup_fee=feature.setup_fee or Decimal('0.00'),
            discount_amount=Decimal('0.00'),
            tax_amount=Decimal('0.00'),
            final_price=price + (feature.setup_fee or Decimal('0.00')),
            limit_override=custom_limit,
            is_active=True
        )
        
        self.db.add(addon)
        await self.db.commit()
        await self.db.refresh(addon)
        
        # Update subscription total
        await self._recalculate_subscription_total(subscription_id)
        
        # Initialize usage tracking if quota-based
        if feature.feature_type == 'quota':
            limit = custom_limit or feature.default_limit
            usage = FeatureUsage(
                id=uuid.uuid4(),
                org_id=subscription.org_id,
                feature_id=feature.id,
                usage_count=0,
                limit_amount=limit,
                period_start=subscription.current_period_start,
                period_end=subscription.current_period_end
            )
            self.db.add(usage)
            await self.db.commit()
        
        return addon

    async def remove_addon(self, addon_id: UUID):
        """Remove an addon from subscription"""
        
        addon_result = await self.db.execute(
            select(SubscriptionAddon).where(SubscriptionAddon.id == addon_id)
        )
        addon = addon_result.scalar_one_or_none()
        
        if not addon:
            raise HttpError(404, "Addon not found", "ADDON_NOT_FOUND")
        
        addon.is_active = False
        addon.removed_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        
        # Update subscription total
        await self._recalculate_subscription_total(addon.subscription_id)

    async def update_addon(
        self,
        addon_id: UUID,
        limit: Optional[int] = None,
        price: Optional[Decimal] = None
    ):
        """Update addon limit and/or price"""
        
        addon_result = await self.db.execute(
            select(SubscriptionAddon).where(SubscriptionAddon.id == addon_id)
        )
        addon = addon_result.scalar_one_or_none()
        
        if not addon:
            raise HttpError(404, "Addon not found", "ADDON_NOT_FOUND")
        
        if limit is not None:
            addon.limit_override = limit
        
        if price is not None:
            addon.unit_price = price
            addon.final_price = price + addon.setup_fee
        
        await self.db.commit()
        
        # Update subscription total
        await self._recalculate_subscription_total(addon.subscription_id)

    # ===================== DISCOUNT APPLICATION =====================

    async def apply_discount(
        self,
        subscription_id: UUID,
        discount_code: str,
        target: str = 'plan',
        addon_id: Optional[UUID] = None
    ) -> Dict:
        """
        Apply discount code to subscription or addon.
        
        Args:
            subscription_id: Subscription ID
            discount_code: Discount code
            target: 'plan' or 'addon'
            addon_id: Required if target is 'addon'
            
        Returns:
            Discount details and amounts saved
        """
        
        # Validate target
        if target == 'addon' and not addon_id:
            raise HttpError(400, "addon_id required for addon target", "MISSING_ADDON_ID")
        
        # Get discount
        discount_result = await self.db.execute(
            select(Discount).where(
                and_(
                    Discount.code == discount_code,
                    Discount.is_active == True,
                    Discount.valid_from <= datetime.now(timezone.utc),
                    or_(
                        Discount.valid_until.is_(None),
                        Discount.valid_until >= datetime.now(timezone.utc)
                    ),
                    or_(
                        Discount.max_uses.is_(None),
                        Discount.current_uses < Discount.max_uses
                    )
                )
            )
        )
        
        discount = discount_result.scalar_one_or_none()
        
        if not discount:
            raise HttpError(400, "Invalid or expired discount code", "INVALID_DISCOUNT")
        
        # Validate applicability
        if target == 'plan' and discount.applies_to not in ['plan', 'both']:
            raise HttpError(400, "Discount not applicable to plans", "INVALID_TARGET")
        
        if target == 'addon' and discount.applies_to not in ['feature', 'both']:
            raise HttpError(400, "Discount not applicable to features", "INVALID_TARGET")
        
        # Get original price
        if target == 'plan':
            sub_result = await self.db.execute(
                select(Subscription).where(Subscription.id == subscription_id)
            )
            subscription = sub_result.scalar_one()
            original_price = subscription.base_amount
        else:
            addon_result = await self.db.execute(
                select(SubscriptionAddon).where(SubscriptionAddon.id == addon_id)
            )
            addon = addon_result.scalar_one()
            original_price = addon.unit_price
        
        # Calculate discount amount
        if discount.discount_type == 'percentage':
            amount = (original_price * discount.discount_value / 100).quantize(Decimal('0.01'))
        else:
            amount = min(discount.discount_value, original_price)
        
        # Respect max discount if set
        if discount.max_discount_amount:
            amount = min(amount, discount.max_discount_amount)
        
        # Save discount application
        sub_discount = SubscriptionDiscount(
            id=uuid.uuid4(),
            subscription_id=subscription_id,
            discount_id=discount.id,
            discount_type=discount.discount_type,
            discount_value=discount.discount_value,
            amount_saved=amount,
            applied_to=target,
            addon_id=addon_id if target == 'addon' else None
        )
        self.db.add(sub_discount)
        
        # Increment usage count
        discount.current_uses += 1
        
        # Update prices
        if target == 'plan':
            subscription.discount_amount += amount
            subscription.total_amount = subscription.base_amount - subscription.discount_amount + subscription.tax_amount
        else:
            addon.discount_amount += amount
            addon.final_price = addon.unit_price - addon.discount_amount + addon.tax_amount
        
        await self.db.commit()
        
        return {
            "discount_code": discount_code,
            "discount_amount": float(amount),
            "original_price": float(original_price),
            "final_price": float(original_price - amount)
        }

    # ===================== SUBSCRIPTION MODIFICATIONS =====================

    async def change_plan(
        self,
        subscription_id: UUID,
        new_plan_slug: str,
        proration: str = 'pro_rata'  # 'pro_rata', 'full_credit', 'no_credit'
    ) -> Subscription:
        """
        Change subscription to different plan.
        Handles proration/credit calculation.
        """
        
        # Get current subscription
        sub_result = await self.db.execute(
            select(Subscription).where(Subscription.id == subscription_id)
        )
        subscription = sub_result.scalar_one_or_none()
        
        if not subscription:
            raise HttpError(404, "Subscription not found", "SUBSCRIPTION_NOT_FOUND")
        
        # Get new plan
        plan_result = await self.db.execute(
            select(Plan).where(
                and_(Plan.slug == new_plan_slug, Plan.is_active == True)
            )
        )
        new_plan = plan_result.scalar_one_or_none()
        
        if not new_plan:
            raise HttpError(404, "Plan not found", "PLAN_NOT_FOUND")
        
        # Calculate proration
        now = datetime.now(timezone.utc)
        days_used = (now - subscription.current_period_start).days
        days_remaining = (subscription.current_period_end - now).days
        total_days = (subscription.current_period_end - subscription.current_period_start).days
        
        old_daily = subscription.base_amount / total_days
        new_daily = new_plan.base_price / total_days
        
        if proration == 'pro_rata':
            # Calculate pro-rata credit
            old_remaining = old_daily * days_remaining
            new_remaining = new_daily * days_remaining
            credit = old_remaining - new_remaining
        elif proration == 'full_credit':
            credit = subscription.base_amount
        else:  # no_credit
            credit = Decimal('0.00')
        
        # Update subscription
        subscription.plan_id = new_plan.id
        subscription.base_amount = new_plan.base_price
        subscription.setup_fee = new_plan.setup_fee or Decimal('0.00')
        
        # Apply credit as discount
        if credit > 0:
            subscription.discount_amount += credit
        
        await self.db.commit()
        await self.db.refresh(subscription)
        
        return subscription

    async def cancel_subscription(
        self,
        subscription_id: UUID,
        immediate: bool = False,
        reason: Optional[str] = None
    ):
        """
        Cancel subscription immediately or at period end.
        
        Args:
            subscription_id: Subscription ID
            immediate: Cancel immediately or at period end
            reason: Cancellation reason
        """
        
        sub_result = await self.db.execute(
            select(Subscription).where(Subscription.id == subscription_id)
        )
        subscription = sub_result.scalar_one_or_none()
        
        if not subscription:
            raise HttpError(404, "Subscription not found", "SUBSCRIPTION_NOT_FOUND")
        
        if immediate:
            subscription.status = 'cancelled'
            subscription.cancelled_at = datetime.now(timezone.utc)
        else:
            subscription.auto_renew = False
        
        if reason:
            subscription.metadata['cancellation_reason'] = reason
        
        await self.db.commit()

    async def reactivate_subscription(self, subscription_id: UUID):
        """Reactivate a cancelled subscription"""
        
        sub_result = await self.db.execute(
            select(Subscription).where(Subscription.id == subscription_id)
        )
        subscription = sub_result.scalar_one_or_none()
        
        if not subscription:
            raise HttpError(404, "Subscription not found", "SUBSCRIPTION_NOT_FOUND")
        
        if subscription.status != 'cancelled':
            raise HttpError(400, "Only cancelled subscriptions can be reactivated", "CANNOT_REACTIVATE")
        
        subscription.status = 'active'
        subscription.auto_renew = True
        subscription.cancelled_at = None
        
        await self.db.commit()

    # ===================== SUBSCRIPTION QUERYING =====================

    async def get_subscription(self, subscription_id: UUID) -> Optional[Subscription]:
        """Get subscription with all details"""
        
        result = await self.db.execute(
            select(Subscription).where(Subscription.id == subscription_id)
        )
        return result.scalar_one_or_none()

    async def get_org_subscription(self, org_id: UUID, active_only: bool = True) -> Optional[Subscription]:
        """Get organization's active subscription"""
        
        query = select(Subscription).where(Subscription.org_id == org_id)
        
        if active_only:
            query = query.where(Subscription.status.in_(['active', 'trialing']))
        
        result = await self.db.execute(query.order_by(Subscription.created_at.desc()).limit(1))
        return result.scalar_one_or_none()

    async def get_subscription_summary(self, org_id: UUID) -> Dict:
        """Get complete subscription details with all pricing info"""
        
        subscription = await self.get_org_subscription(org_id)
        
        if not subscription:
            return {
                "has_subscription": False,
                "message": "No active subscription"
            }
        
        # Get plan
        plan_result = await self.db.execute(
            select(Plan).where(Plan.id == subscription.plan_id)
        )
        plan = plan_result.scalar_one()
        
        # Get addons
        addons_result = await self.db.execute(
            select(SubscriptionAddon, Feature).join(
                Feature, Feature.id == SubscriptionAddon.feature_id
            ).where(
                and_(
                    SubscriptionAddon.subscription_id == subscription.id,
                    SubscriptionAddon.is_active == True
                )
            )
        )
        addons_data = addons_result.all()
        
        addons = []
        addons_total = Decimal('0.00')
        addons_discount = Decimal('0.00')
        
        for addon, feature in addons_data:
            addons.append({
                "id": str(addon.id),
                "name": feature.name,
                "slug": feature.slug,
                "type": feature.feature_type,
                "base_price": float(addon.unit_price),
                "setup_fee": float(addon.setup_fee),
                "discount": float(addon.discount_amount),
                "tax": float(addon.tax_amount),
                "final_price": float(addon.final_price),
                "limit": addon.limit_override or feature.default_limit
            })
            addons_total += addon.final_price
            addons_discount += addon.discount_amount
        
        # Calculate totals
        plan_price = subscription.base_amount - subscription.discount_amount + subscription.tax_amount
        
        return {
            "has_subscription": True,
            "subscription_id": str(subscription.id),
            "status": subscription.status,
            "plan": {
                "id": str(plan.id),
                "name": plan.name,
                "slug": plan.slug,
                "base_price": float(subscription.base_amount),
                "setup_fee": float(subscription.setup_fee),
                "discount": float(subscription.discount_amount),
                "tax": float(subscription.tax_amount),
                "final_price": float(plan_price)
            },
            "addons": addons,
            "billing": {
                "subtotal": float(subscription.base_amount + addons_total),
                "discounts": float(subscription.discount_amount + addons_discount),
                "tax": float(subscription.tax_amount),
                "total": float(subscription.total_amount),
                "currency": "USD",
                "interval": plan.billing_interval,
                "auto_renew": subscription.auto_renew
            },
            "period": {
                "current_start": subscription.current_period_start.isoformat(),
                "current_end": subscription.current_period_end.isoformat(),
                "trial_end": subscription.trial_end.isoformat() if subscription.trial_end else None
            }
        }

    # ===================== PRIVATE HELPER METHODS =====================

    async def _initialize_usage_tracking(self, org_id: UUID, subscription_id: UUID):
        """Initialize usage tracking for all quota-based features in subscription"""
        
        subscription = await self.get_subscription(subscription_id)
        
        # Get quota features from plan
        plan_features = await self.db.execute(
            select(Feature, PlanFeature).join(
                PlanFeature, PlanFeature.feature_id == Feature.id
            ).where(
                and_(
                    PlanFeature.plan_id == subscription.plan_id,
                    Feature.feature_type == 'quota',
                    Feature.is_active == True
                )
            )
        )
        
        for feature, plan_feature in plan_features:
            limit = plan_feature.limit_override or feature.default_limit
            
            usage = FeatureUsage(
                id=uuid.uuid4(),
                org_id=org_id,
                feature_id=feature.id,
                usage_count=0,
                limit_amount=limit,
                period_start=subscription.current_period_start,
                period_end=subscription.current_period_end
            )
            self.db.add(usage)
        
        await self.db.commit()

    async def _recalculate_subscription_total(self, subscription_id: UUID):
        """Recalculate subscription total with all addons and adjustments"""
        
        # Get subscription and addons
        query = text("""
            SELECT 
                s.base_amount,
                s.setup_fee,
                s.discount_amount as plan_discount,
                s.tax_amount,
                COALESCE(SUM(sa.final_price), 0) as addons_total,
                COALESCE(SUM(sa.discount_amount), 0) as addons_discount
            FROM subscriptions s
            LEFT JOIN subscription_addons sa ON sa.subscription_id = s.id AND sa.is_active = true
            WHERE s.id = :sub_id
            GROUP BY s.id
        """)
        
        result = await self.db.execute(query, {"sub_id": str(subscription_id)})
        totals = result.fetchone()
        
        if totals:
            total = (totals[0] + totals[1] - totals[2] + totals[3] + totals[4])
            
            update_query = text("""
                UPDATE subscriptions
                SET total_amount = :total
                WHERE id = :sub_id
            """)
            
            await self.db.execute(update_query, {
                "total": total,
                "sub_id": str(subscription_id)
            })
            
            await self.db.commit()
