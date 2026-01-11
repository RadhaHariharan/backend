"""
Billing & Usage Tracking Service
Handles feature access checking, quota enforcement, and usage tracking
"""

from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import UUID
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, text, update

from models.subscription import Feature, FeatureUsage, Subscription, SubscriptionAddon
from utils.response import HttpError


class BillingService:
    """
    Advanced billing service for feature access, quota management, and usage tracking.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db

    # ===================== FEATURE ACCESS CHECKING =====================

    async def has_feature_access(self, org_id: UUID, feature_slug: str) -> bool:
        """
        Check if organization has access to a feature.
        Works for all feature types (boolean, quota, unlimited).
        """
        
        # Check plan features
        plan_access = await self.db.execute(
            text("""
                SELECT 1
                FROM subscriptions s
                JOIN plan_features pf ON pf.plan_id = s.plan_id
                JOIN features f ON f.id = pf.feature_id
                WHERE s.org_id = :org_id
                AND f.slug = :feature_slug
                AND s.status IN ('active', 'trialing')
                LIMIT 1
            """),
            {"org_id": str(org_id), "feature_slug": feature_slug}
        )
        
        if plan_access.fetchone():
            return True
        
        # Check addons
        addon_access = await self.db.execute(
            text("""
                SELECT 1
                FROM subscription_addons sa
                JOIN subscriptions s ON s.id = sa.subscription_id
                JOIN features f ON f.id = sa.feature_id
                WHERE s.org_id = :org_id
                AND f.slug = :feature_slug
                AND sa.is_active = true
                AND s.status IN ('active', 'trialing')
                LIMIT 1
            """),
            {"org_id": str(org_id), "feature_slug": feature_slug}
        )
        
        return bool(addon_access.fetchone())

    async def get_feature_status(
        self,
        org_id: UUID,
        feature_slug: str
    ) -> Dict:
        """
        Get comprehensive feature status for organization.
        
        Returns:
            {
                'has_access': bool,
                'feature_type': 'boolean|quota|unlimited',
                'status': 'included_in_plan|added_as_addon|not_available',
                'current_usage': int (for quota),
                'limit': int (for quota),
                'remaining': int (for quota),
                'resets_at': datetime (for quota),
                'unlimited': bool
            }
        """
        
        # Get feature
        feature_result = await self.db.execute(
            select(Feature).where(Feature.slug == feature_slug)
        )
        feature = feature_result.scalar_one_or_none()
        
        if not feature or not feature.is_active:
            return {
                'has_access': False,
                'status': 'not_available',
                'reason': 'feature_not_found'
            }
        
        # Check plan inclusion
        plan_check = await self.db.execute(
            text("""
                SELECT pf.limit_override, f.default_limit, f.feature_type
                FROM subscriptions s
                JOIN plan_features pf ON pf.plan_id = s.plan_id
                JOIN features f ON f.id = pf.feature_id
                WHERE s.org_id = :org_id
                AND f.slug = :feature_slug
                AND s.status IN ('active', 'trialing')
                LIMIT 1
            """),
            {"org_id": str(org_id), "feature_slug": feature_slug}
        )
        
        plan_feature = plan_check.fetchone()
        status = 'not_available'
        
        if plan_feature:
            status = 'included_in_plan'
            in_plan = True
        else:
            in_plan = False
        
        # Check addon
        addon_check = await self.db.execute(
            text("""
                SELECT sa.limit_override, f.default_limit
                FROM subscription_addons sa
                JOIN subscriptions s ON s.id = sa.subscription_id
                JOIN features f ON f.id = sa.feature_id
                WHERE s.org_id = :org_id
                AND f.slug = :feature_slug
                AND sa.is_active = true
                AND s.status IN ('active', 'trialing')
                LIMIT 1
            """),
            {"org_id": str(org_id), "feature_slug": feature_slug}
        )
        
        addon = addon_check.fetchone()
        if addon:
            status = 'added_as_addon'
            in_addon = True
        else:
            in_addon = False
        
        # If no access at all
        if not in_plan and not in_addon:
            return {
                'has_access': False,
                'feature_type': feature.feature_type,
                'status': status,
                'reason': 'feature_not_included_or_purchased'
            }
        
        # Prepare response
        response = {
            'has_access': True,
            'feature_type': feature.feature_type,
            'status': status,
            'feature_id': str(feature.id),
            'feature_name': feature.name,
            'unlimited': feature.feature_type == 'unlimited'
        }
        
        # For quota features, get usage info
        if feature.feature_type == 'quota':
            usage_data = await self.check_quota(org_id, feature_slug)
            response.update(usage_data)
        
        return response

    # ===================== QUOTA CHECKING & ENFORCEMENT =====================

    async def check_quota(self, org_id: UUID, feature_slug: str) -> Dict:
        """
        Check current quota usage for a feature.
        
        Returns:
            {
                'has_access': bool,
                'current': int,
                'limit': int (or None for unlimited),
                'remaining': int (or None),
                'usage_percent': float,
                'resets_at': datetime,
                'warning': bool (if > 80%)
            }
        """
        
        result = await self.db.execute(
            text("""
                SELECT 
                    fu.usage_count,
                    fu.limit_amount,
                    fu.period_end
                FROM feature_usage fu
                JOIN features f ON f.id = fu.feature_id
                WHERE fu.org_id = :org_id
                AND f.slug = :feature_slug
                AND fu.period_end > NOW()
                ORDER BY fu.created_at DESC
                LIMIT 1
            """),
            {"org_id": str(org_id), "feature_slug": feature_slug}
        )
        
        usage = result.fetchone()
        
        if not usage:
            return {
                'has_access': False,
                'reason': 'no_quota_tracking',
                'current': 0,
                'limit': None,
                'remaining': None
            }
        
        current = usage[0]
        limit = usage[1]
        period_end = usage[2]
        
        # Calculate metrics
        if limit is None:
            return {
                'has_access': True,
                'current': current,
                'limit': None,
                'remaining': None,
                'unlimited': True,
                'usage_percent': 0,
                'warning': False,
                'resets_at': period_end.isoformat()
            }
        
        remaining = limit - current
        has_access = remaining > 0
        usage_percent = (current / limit * 100) if limit > 0 else 0
        warning = usage_percent >= 80
        
        return {
            'has_access': has_access,
            'current': current,
            'limit': limit,
            'remaining': max(0, remaining),
            'unlimited': False,
            'usage_percent': round(usage_percent, 2),
            'warning': warning,
            'resets_at': period_end.isoformat()
        }

    async def get_org_feature_limits(self, org_id: UUID) -> Dict[str, Dict]:
        """Get all feature limits and usage for organization"""
        
        result = await self.db.execute(
            text("""
                SELECT 
                    f.slug,
                    f.name,
                    f.feature_type,
                    fu.usage_count,
                    fu.limit_amount,
                    fu.period_end
                FROM features f
                LEFT JOIN feature_usage fu ON f.id = fu.feature_id AND fu.org_id = :org_id AND fu.period_end > NOW()
                WHERE (fu.id IS NOT NULL OR f.feature_type IN ('boolean', 'unlimited'))
                ORDER BY f.display_order
            """),
            {"org_id": str(org_id)}
        )
        
        features = {}
        for row in result:
            slug = row[0]
            name = row[1]
            feature_type = row[2]
            usage_count = row[3]
            limit_amount = row[4]
            period_end = row[5]
            
            if feature_type == 'boolean':
                features[slug] = {
                    'name': name,
                    'type': 'boolean',
                    'enabled': await self.has_feature_access(org_id, slug)
                }
            else:
                has_access = usage_count is not None and (limit_amount is None or usage_count < limit_amount)
                features[slug] = {
                    'name': name,
                    'type': feature_type,
                    'current': usage_count or 0,
                    'limit': limit_amount,
                    'remaining': (limit_amount - (usage_count or 0)) if limit_amount else None,
                    'usage_percent': ((usage_count or 0) / limit_amount * 100) if limit_amount else 0,
                    'has_access': has_access,
                    'resets_at': period_end.isoformat() if period_end else None
                }
        
        return features

    # ===================== USAGE TRACKING =====================

    async def increment_usage(
        self,
        org_id: UUID,
        feature_slug: str,
        amount: int = 1,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Increment usage counter for a quota-based feature.
        Respects limits and raises error if quota exceeded.
        
        Args:
            org_id: Organization ID
            feature_slug: Feature slug
            amount: Amount to increment
            metadata: Additional metadata
            
        Returns:
            Updated quota status
            
        Raises:
            HttpError: If quota exceeded or feature not available
        """
        
        # Check access before incrementing
        quota_status = await self.check_quota(org_id, feature_slug)
        
        if not quota_status.get('has_access'):
            raise HttpError(
                403,
                f"Quota exceeded for {feature_slug}. Current: {quota_status.get('current')}/{quota_status.get('limit')}",
                "QUOTA_EXCEEDED"
            )
        
        if quota_status['remaining'] and quota_status['remaining'] < amount:
            raise HttpError(
                403,
                f"Insufficient quota. Available: {quota_status['remaining']}, Requested: {amount}",
                "INSUFFICIENT_QUOTA"
            )
        
        # Update usage
        update_query = text("""
            UPDATE feature_usage fu
            SET usage_count = usage_count + :amount,
                updated_at = NOW(),
                metadata = COALESCE(metadata, '{}'::jsonb) || :metadata
            FROM features f
            WHERE f.id = fu.feature_id
            AND fu.org_id = :org_id
            AND f.slug = :feature_slug
            AND fu.period_end > NOW()
        """)
        
        await self.db.execute(
            update_query,
            {
                "org_id": str(org_id),
                "feature_slug": feature_slug,
                "amount": amount,
                "metadata": metadata or {}
            }
        )
        
        await self.db.commit()
        
        # Return updated status
        return await self.check_quota(org_id, feature_slug)

    async def reset_usage(self, org_id: UUID, feature_slug: str):
        """Reset usage counter for a feature (admin only)"""
        
        update_query = text("""
            UPDATE feature_usage fu
            SET usage_count = 0,
                updated_at = NOW(),
                reset_warning_sent = false,
                exceeded_notification_sent = false
            FROM features f
            WHERE f.id = fu.feature_id
            AND fu.org_id = :org_id
            AND f.slug = :feature_slug
        """)
        
        await self.db.execute(
            update_query,
            {"org_id": str(org_id), "feature_slug": feature_slug}
        )
        
        await self.db.commit()

    async def batch_increment_usage(
        self,
        org_id: UUID,
        usages: Dict[str, int]  # {feature_slug: amount}
    ) -> Dict[str, Dict]:
        """
        Increment multiple features at once.
        All or nothing - if any fails, none are updated.
        """
        
        results = {}
        
        # Validate all before updating any
        for feature_slug, amount in usages.items():
            quota_status = await self.check_quota(org_id, feature_slug)
            
            if not quota_status.get('has_access'):
                raise HttpError(
                    403,
                    f"Quota exceeded for {feature_slug}",
                    "QUOTA_EXCEEDED"
                )
            
            if quota_status['remaining'] and quota_status['remaining'] < amount:
                raise HttpError(
                    403,
                    f"Insufficient quota for {feature_slug}",
                    "INSUFFICIENT_QUOTA"
                )
        
        # All validated, now update all
        for feature_slug, amount in usages.items():
            result = await self.increment_usage(org_id, feature_slug, amount)
            results[feature_slug] = result
        
        return results

    async def get_usage_analytics(self, org_id: UUID) -> Dict:
        """Get usage analytics across all features"""
        
        result = await self.db.execute(
            text("""
                SELECT 
                    f.slug,
                    f.name,
                    COUNT(fu.id) as periods_tracked,
                    SUM(fu.usage_count) as total_usage,
                    AVG(fu.usage_count) as avg_usage_per_period,
                    MAX(fu.usage_count) as max_usage_in_period,
                    MAX(fu.limit_amount) as limit
                FROM features f
                LEFT JOIN feature_usage fu ON f.id = fu.feature_id AND fu.org_id = :org_id
                GROUP BY f.id, f.slug, f.name
                ORDER BY f.display_order
            """),
            {"org_id": str(org_id)}
        )
        
        analytics = {}
        for row in result:
            slug = row[0]
            analytics[slug] = {
                'name': row[1],
                'periods_tracked': row[2] or 0,
                'total_usage': row[3] or 0,
                'avg_per_period': float(row[4] or 0),
                'peak_usage': row[5] or 0,
                'limit': row[6]
            }
        
        return analytics

    # ===================== FEATURE LIMITS MANAGEMENT =====================

    async def override_feature_limit(
        self,
        org_id: UUID,
        feature_slug: str,
        new_limit: int
    ):
        """Override default limit for a feature (e.g., negotiated custom plan)"""
        
        # Get current usage record
        current = await self.db.execute(
            text("""
                SELECT fu.id, fu.usage_count
                FROM feature_usage fu
                JOIN features f ON f.id = fu.feature_id
                WHERE fu.org_id = :org_id
                AND f.slug = :feature_slug
                AND fu.period_end > NOW()
                ORDER BY fu.created_at DESC
                LIMIT 1
            """),
            {"org_id": str(org_id), "feature_slug": feature_slug}
        )
        
        usage = current.fetchone()
        
        if not usage:
            raise HttpError(400, "No active usage tracking for feature", "NO_USAGE_TRACKING")
        
        # Check if override would violate current usage
        usage_count = usage[1]
        if usage_count > new_limit:
            raise HttpError(
                400,
                f"Cannot set limit to {new_limit} when already used {usage_count}",
                "LIMIT_BELOW_CURRENT_USAGE"
            )
        
        # Update limit
        update_query = text("""
            UPDATE feature_usage
            SET limit_amount = :new_limit,
                updated_at = NOW()
            WHERE id = :usage_id
        """)
        
        await self.db.execute(
            update_query,
            {"new_limit": new_limit, "usage_id": usage[0]}
        )
        
        await self.db.commit()
