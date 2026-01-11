"""
Database seeding script for subscription plans and features
Run with: python -m scripts.seed_subscription_data
"""

import asyncio
import sys
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import models
from models.base import Base
from models.subscription import Plan, Feature, PlanFeature, Discount


async def seed_plans(session: AsyncSession):
    """Create default subscription plans"""
    
    # Check if plans exist
    existing = await session.execute(select(Plan).limit(1))
    if existing.scalars().first():
        print("✓ Plans already exist, skipping...")
        return
    
    plans = [
        Plan(
            id=uuid4(),
            slug="beginner",
            name="Beginner",
            description="Perfect for getting started with basic analytics and features",
            base_price=Decimal("9.99"),
            setup_fee=Decimal("0"),
            billing_interval="monthly",
            max_features=3,
            trial_days=14,
            is_active=True,
            metadata={
                "color": "blue",
                "recommended": False,
                "popular": False
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        ),
        Plan(
            id=uuid4(),
            slug="pro",
            name="Pro",
            description="For growing teams with advanced features and priority support",
            base_price=Decimal("29.99"),
            setup_fee=Decimal("0"),
            billing_interval="monthly",
            max_features=10,
            trial_days=14,
            is_active=True,
            metadata={
                "color": "green",
                "recommended": True,
                "popular": True
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        ),
        Plan(
            id=uuid4(),
            slug="expert",
            name="Expert",
            description="Enterprise solution with unlimited features and dedicated support",
            base_price=Decimal("99.99"),
            setup_fee=Decimal("99.00"),
            billing_interval="monthly",
            max_features=-1,  # Unlimited
            trial_days=30,
            is_active=True,
            metadata={
                "color": "gold",
                "recommended": False,
                "popular": False,
                "includes_onboarding": True,
                "includes_dedicated_support": True
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
    ]
    
    for plan in plans:
        session.add(plan)
    
    await session.commit()
    print(f"✓ Created {len(plans)} plans")


async def seed_features(session: AsyncSession):
    """Create billable features"""
    
    # Check if features exist
    existing = await session.execute(select(Feature).limit(1))
    if existing.scalars().first():
        print("✓ Features already exist, skipping...")
        return
    
    features = [
        # Boolean features
        Feature(
            id=uuid4(),
            slug="advanced_analytics",
            name="Advanced Analytics",
            description="Access to detailed analytics dashboards and custom reports",
            feature_type="boolean",
            standalone_price=Decimal("29.99"),
            customizable=False,
            is_active=True,
            display_order=1,
            metadata={
                "category": "analytics",
                "icon": "chart-bar"
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        ),
        Feature(
            id=uuid4(),
            slug="bulk_export",
            name="Bulk Export",
            description="Export data in bulk using CSV, JSON, or custom formats",
            feature_type="boolean",
            standalone_price=Decimal("49.99"),
            customizable=False,
            is_active=True,
            display_order=2,
            metadata={
                "category": "data_management",
                "icon": "download"
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        ),
        Feature(
            id=uuid4(),
            slug="white_label",
            name="White Label",
            description="Remove branding and customize with your own colors and logo",
            feature_type="boolean",
            standalone_price=Decimal("79.99"),
            customizable=False,
            is_active=True,
            display_order=3,
            metadata={
                "category": "customization",
                "icon": "palette"
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        ),
        # Quota features
        Feature(
            id=uuid4(),
            slug="api_requests",
            name="API Requests",
            description="Number of API requests per month",
            feature_type="quota",
            default_limit=1000,
            standalone_price=Decimal("0.01"),  # $0.01 per request above limit
            customizable=True,
            is_active=True,
            display_order=4,
            metadata={
                "category": "api",
                "unit": "requests",
                "billing_method": "overage"
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        ),
        Feature(
            id=uuid4(),
            slug="storage_gb",
            name="Data Storage",
            description="GB of data storage",
            feature_type="quota",
            default_limit=10,
            standalone_price=Decimal("5.00"),  # $5 per GB
            customizable=True,
            is_active=True,
            display_order=5,
            metadata={
                "category": "storage",
                "unit": "GB",
                "billing_method": "fixed_per_unit"
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        ),
        Feature(
            id=uuid4(),
            slug="email_sends",
            name="Email Sends",
            description="Number of emails you can send per month",
            feature_type="quota",
            default_limit=5000,
            standalone_price=Decimal("0.001"),  # $0.001 per email
            customizable=True,
            is_active=True,
            display_order=6,
            metadata={
                "category": "email",
                "unit": "emails",
                "billing_method": "overage"
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        ),
        # Unlimited features
        Feature(
            id=uuid4(),
            slug="user_management",
            name="User Management",
            description="Create and manage unlimited team members",
            feature_type="unlimited",
            standalone_price=Decimal("0"),
            customizable=False,
            is_active=True,
            display_order=7,
            metadata={
                "category": "collaboration",
                "included_in_all_plans": True
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        ),
        Feature(
            id=uuid4(),
            slug="priority_support",
            name="Priority Support",
            description="Get priority responses to support tickets (24/7 for Expert plan)",
            feature_type="unlimited",
            standalone_price=Decimal("49.99"),
            customizable=False,
            is_active=True,
            display_order=8,
            metadata={
                "category": "support",
                "sla_hours": {
                    "pro": 24,
                    "expert": 1
                }
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
    ]
    
    for feature in features:
        session.add(feature)
    
    await session.commit()
    print(f"✓ Created {len(features)} features")


async def seed_plan_features(session: AsyncSession):
    """Map features to plans"""
    
    # Check if mappings exist
    existing = await session.execute(select(PlanFeature).limit(1))
    if existing.scalars().first():
        print("✓ Plan features already exist, skipping...")
        return
    
    # Get all plans and features
    plans_result = await session.execute(select(Plan))
    plans = {p.slug: p for p in plans_result.scalars()}
    
    features_result = await session.execute(select(Feature))
    features = {f.slug: f for f in features_result.scalars()}
    
    # Define feature inclusions per plan
    plan_features = [
        # Beginner plan
        ("beginner", "api_requests", 1000),
        ("beginner", "storage_gb", 5),
        ("beginner", "email_sends", 1000),
        ("beginner", "user_management", None),  # Unlimited
        
        # Pro plan - includes all Beginner features plus more
        ("pro", "api_requests", 10000),
        ("pro", "storage_gb", 100),
        ("pro", "email_sends", 50000),
        ("pro", "user_management", None),
        ("pro", "advanced_analytics", None),  # Boolean feature
        ("pro", "priority_support", None),
        
        # Expert plan - everything unlimited
        ("expert", "api_requests", None),  # Unlimited
        ("expert", "storage_gb", None),
        ("expert", "email_sends", None),
        ("expert", "user_management", None),
        ("expert", "advanced_analytics", None),
        ("expert", "bulk_export", None),
        ("expert", "white_label", None),
        ("expert", "priority_support", None),
    ]
    
    for plan_slug, feature_slug, limit in plan_features:
        plan = plans.get(plan_slug)
        feature = features.get(feature_slug)
        
        if plan and feature:
            pf = PlanFeature(
                id=uuid4(),
                plan_id=plan.id,
                feature_id=feature.id,
                limit_override=limit
            )
            session.add(pf)
    
    await session.commit()
    print(f"✓ Created {len(plan_features)} plan-feature mappings")


async def seed_discounts(session: AsyncSession):
    """Create sample discount codes"""
    
    # Check if discounts exist
    existing = await session.execute(select(Discount).limit(1))
    if existing.scalars().first():
        print("✓ Discounts already exist, skipping...")
        return
    
    discounts = [
        Discount(
            id=uuid4(),
            code="WELCOME10",
            description="10% off for new customers",
            discount_type="percentage",
            discount_value=Decimal("10"),
            applies_to="subscription",
            max_redemptions=1000,
            current_redemptions=0,
            is_active=True,
            metadata={
                "campaign": "new_user",
                "created_by": "admin"
            },
            created_at=datetime.now(timezone.utc)
        ),
        Discount(
            id=uuid4(),
            code="ANNUAL20",
            description="20% off annual billing",
            discount_type="percentage",
            discount_value=Decimal("20"),
            applies_to="subscription",
            max_redemptions=None,  # Unlimited
            current_redemptions=0,
            is_active=True,
            metadata={
                "campaign": "annual_billing",
                "created_by": "admin"
            },
            created_at=datetime.now(timezone.utc)
        ),
        Discount(
            id=uuid4(),
            code="SAVE25",
            description="$25 off orders over $100",
            discount_type="fixed",
            discount_value=Decimal("25"),
            applies_to="subscription",
            max_redemptions=500,
            current_redemptions=0,
            is_active=True,
            metadata={
                "campaign": "summer_sale",
                "min_order_value": 100,
                "created_by": "admin"
            },
            created_at=datetime.now(timezone.utc)
        ),
        Discount(
            id=uuid4(),
            code="ANALYTICS50",
            description="50% off Advanced Analytics addon",
            discount_type="percentage",
            discount_value=Decimal("50"),
            applies_to="addon",
            max_redemptions=100,
            current_redemptions=0,
            is_active=True,
            metadata={
                "campaign": "feature_promotion",
                "target_feature": "advanced_analytics",
                "created_by": "admin"
            },
            created_at=datetime.now(timezone.utc)
        )
    ]
    
    for discount in discounts:
        session.add(discount)
    
    await session.commit()
    print(f"✓ Created {len(discounts)} discount codes")


async def main():
    """Main seeding function"""
    
    # Get database URL from environment or use default
    database_url = "postgresql+asyncpg://user:password@localhost/app_db"
    
    # Create engine
    engine = create_async_engine(database_url, echo=False)
    
    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        print("\n🌱 Seeding subscription data...\n")
        
        await seed_plans(session)
        await seed_features(session)
        await seed_plan_features(session)
        await seed_discounts(session)
        
        print("\n✅ Seeding complete!\n")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
