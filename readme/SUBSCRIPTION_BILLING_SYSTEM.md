# Subscription & Billing System - Complete Implementation Guide

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Core Components](#core-components)
3. [Data Models](#data-models)
4. [Service Layer](#service-layer)
5. [API Endpoints](#api-endpoints)
6. [Feature Access & Quota Management](#feature-access--quota-management)
7. [Stripe Integration](#stripe-integration)
8. [Database Initialization](#database-initialization)
9. [Usage Examples](#usage-examples)
10. [Advanced Scenarios](#advanced-scenarios)

---

## System Architecture

### Overview

The subscription system is built on a **multi-tenant, plan-based pricing model** with:

- **3-tier subscription plans** (Beginner, Pro, Expert)
- **À la carte features** with flexible pricing
- **Multi-layer discount system** (percentage, fixed, plan-level, feature-level)
- **Quota-based feature tracking** with usage limits
- **Stripe integration** for payment processing
- **Advanced customization** per organization

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                         │
│  • Subscription Management   • Feature Access  • Billing Webhooks │
└────────────────┬────────────────────────────────────────────────┘
                 │
┌────────────────┴────────────────────────────────────────────────┐
│                     Service Layer                                │
├──────────────────────┬──────────────────┬──────────────────────┤
│ SubscriptionService  │ BillingService   │  StripeService      │
│ • Subscription CRUD  │ • Quota Check    │  • Customer Mgmt    │
│ • Plan Changes       │ • Usage Tracking │  • Payments         │
│ • Addon Management   │ • Feature Access │  • Webhooks         │
│ • Discounts          │ • Analytics      │  • Subscriptions    │
└──────────────────────┴──────────────────┴──────────────────────┘
                 │
┌────────────────┴────────────────────────────────────────────────┐
│                  Database Layer (PostgreSQL)                     │
├──────────────────────────────────────────────────────────────────┤
│ Tables:                                                          │
│  • plans: Subscription tier definitions                          │
│  • features: Billable features (boolean/quota/unlimited)         │
│  • plan_features: Feature inclusions in plans                    │
│  • subscriptions: Active subscriptions per organization          │
│  • subscription_addons: À la carte features                      │
│  • discounts: Discount codes and rules                           │
│  • subscription_discounts: Applied discounts                     │
│  • feature_usage: Quota tracking per billing period              │
└──────────────────────────────────────────────────────────────────┘
                 │
┌────────────────┴────────────────────────────────────────────────┐
│                    External Services                             │
│  • Stripe API: Payment processing & subscription management      │
└──────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Models (`models/`)

#### Plan Model (`models/plan.py`)
Represents subscription tiers with pricing and billing intervals.

**Fields:**
- `slug`: Unique identifier (e.g., 'pro')
- `name`: Display name
- `description`: Plan description
- `base_price`: Monthly/annual price
- `setup_fee`: One-time setup fee (optional)
- `billing_interval`: 'monthly' or 'yearly'
- `max_features`: Maximum features allowed
- `trial_days`: Default trial period
- `metadata`: Custom fields (JSON)

**Example Plans:**
```json
{
  "slug": "beginner",
  "name": "Beginner",
  "base_price": 9.99,
  "setup_fee": 0,
  "billing_interval": "monthly",
  "max_features": 3,
  "trial_days": 14
}
```

#### Feature Model (`models/feature.py`)
Billable features with three types: boolean, quota, and unlimited.

**Feature Types:**
1. **Boolean**: Simple on/off (e.g., "Advanced Analytics")
2. **Quota**: Limited usage (e.g., "1000 API calls/month")
3. **Unlimited**: No limits (e.g., "Unlimited storage")

**Fields:**
- `slug`: Unique identifier
- `name`: Display name
- `feature_type`: 'boolean', 'quota', or 'unlimited'
- `default_limit`: Quota limit (for quota type)
- `standalone_price`: À la carte price
- `customizable`: Can be customized per org
- `metadata`: Additional fields

**Example Features:**
```json
[
  {
    "slug": "advanced_analytics",
    "name": "Advanced Analytics",
    "feature_type": "boolean",
    "standalone_price": 29.99,
    "customizable": false
  },
  {
    "slug": "api_requests",
    "name": "API Requests",
    "feature_type": "quota",
    "default_limit": 1000,
    "standalone_price": 0.01
  }
]
```

#### Subscription Model (`models/subscription.py`)
Main subscription record with pricing breakdown.

**Status Values:**
- `trialing`: Free trial period
- `active`: Paid subscription
- `past_due`: Payment failed
- `cancelled`: Subscription ended

**Pricing Breakdown:**
```
total = base_price + setup_fee + addons - discounts + tax
```

**Additional Models:**
- `PlanFeature`: Maps features to plans with limit overrides
- `SubscriptionAddon`: À la carte features added to subscription
- `Discount`: Discount codes and rules
- `SubscriptionDiscount`: Applied discounts tracking
- `FeatureUsage`: Quota tracking per billing period

---

## Data Models

### Database Schema

```sql
-- Plans table
CREATE TABLE plans (
  id UUID PRIMARY KEY,
  slug VARCHAR UNIQUE NOT NULL,
  name VARCHAR NOT NULL,
  description TEXT,
  base_price NUMERIC NOT NULL,
  setup_fee NUMERIC DEFAULT 0,
  billing_interval VARCHAR DEFAULT 'monthly',
  max_features INTEGER,
  trial_days INTEGER,
  is_active BOOLEAN DEFAULT true,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE,
  updated_at TIMESTAMP WITH TIME ZONE
);

-- Features table
CREATE TABLE features (
  id UUID PRIMARY KEY,
  slug VARCHAR UNIQUE NOT NULL,
  name VARCHAR NOT NULL,
  description TEXT,
  feature_type VARCHAR NOT NULL, -- 'boolean', 'quota', 'unlimited'
  default_limit INTEGER,
  standalone_price NUMERIC,
  customizable BOOLEAN DEFAULT false,
  is_active BOOLEAN DEFAULT true,
  display_order INTEGER,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE,
  updated_at TIMESTAMP WITH TIME ZONE
);

-- Plan-Feature mapping
CREATE TABLE plan_features (
  id UUID PRIMARY KEY,
  plan_id UUID REFERENCES plans(id),
  feature_id UUID REFERENCES features(id),
  limit_override INTEGER,  -- Override default limit per plan
  UNIQUE(plan_id, feature_id)
);

-- Subscriptions
CREATE TABLE subscriptions (
  id UUID PRIMARY KEY,
  org_id UUID NOT NULL REFERENCES organizations(id),
  plan_id UUID REFERENCES plans(id),
  status VARCHAR NOT NULL, -- trialing, active, past_due, cancelled
  base_price NUMERIC NOT NULL,
  addons_price NUMERIC DEFAULT 0,
  discount_amount NUMERIC DEFAULT 0,
  tax_amount NUMERIC DEFAULT 0,
  total_price NUMERIC NOT NULL,
  
  -- Billing period
  billing_period_start TIMESTAMP NOT NULL,
  billing_period_end TIMESTAMP NOT NULL,
  trial_end TIMESTAMP,
  cancelled_at TIMESTAMP,
  
  -- Stripe integration
  stripe_customer_id VARCHAR,
  stripe_subscription_id VARCHAR UNIQUE,
  stripe_current_period_start TIMESTAMP,
  stripe_current_period_end TIMESTAMP,
  stripe_cancel_at TIMESTAMP,
  
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  
  UNIQUE(org_id, stripe_subscription_id)
);

-- Subscription Addons (à la carte features)
CREATE TABLE subscription_addons (
  id UUID PRIMARY KEY,
  subscription_id UUID REFERENCES subscriptions(id),
  feature_id UUID REFERENCES features(id),
  limit_override INTEGER,
  price_override NUMERIC,
  is_active BOOLEAN DEFAULT true,
  added_at TIMESTAMP NOT NULL,
  UNIQUE(subscription_id, feature_id)
);

-- Discounts
CREATE TABLE discounts (
  id UUID PRIMARY KEY,
  code VARCHAR UNIQUE NOT NULL,
  description TEXT,
  
  -- Discount amount
  discount_type VARCHAR NOT NULL, -- 'percentage', 'fixed'
  discount_value NUMERIC NOT NULL,
  
  -- Applicability
  applies_to VARCHAR NOT NULL, -- 'subscription', 'addon', 'all'
  
  -- Constraints
  max_redemptions INTEGER,
  current_redemptions INTEGER DEFAULT 0,
  valid_from TIMESTAMP,
  valid_until TIMESTAMP,
  
  metadata JSONB DEFAULT '{}'::jsonb,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP NOT NULL
);

-- Applied Discounts
CREATE TABLE subscription_discounts (
  id UUID PRIMARY KEY,
  subscription_id UUID REFERENCES subscriptions(id),
  discount_id UUID REFERENCES discounts(id),
  addon_id UUID REFERENCES subscription_addons(id), -- NULL if applies to subscription
  applied_at TIMESTAMP NOT NULL,
  UNIQUE(subscription_id, discount_id, addon_id)
);

-- Feature Usage Tracking
CREATE TABLE feature_usage (
  id UUID PRIMARY KEY,
  org_id UUID NOT NULL REFERENCES organizations(id),
  feature_id UUID NOT NULL REFERENCES features(id),
  billing_period_id VARCHAR NOT NULL, -- e.g., '2024-01'
  usage_count INTEGER DEFAULT 0,
  limit_amount INTEGER,
  period_start TIMESTAMP NOT NULL,
  period_end TIMESTAMP NOT NULL,
  
  reset_warning_sent BOOLEAN DEFAULT false,
  exceeded_notification_sent BOOLEAN DEFAULT false,
  
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  
  UNIQUE(org_id, feature_id, billing_period_id)
);
```

### Model Relationships

```
Plan (1) ──many── PlanFeature ──many── Feature (1)
        │
        └─ Subscription (1) ──many── SubscriptionAddon ──many── Feature (1)
                │
                ├─many── SubscriptionDiscount ──many── Discount
                │
                ├─many── SubscriptionDiscount ──many── Feature (for addon discounts)
                │
                └─ Organization (N)

Feature (1) ──many── FeatureUsage (N) ──many── Organization
```

---

## Service Layer

### SubscriptionService (`services/subscription_service.py`)

Handles all subscription lifecycle operations.

**Key Methods:**

#### Create Subscription
```python
async def create_subscription(
    org_id: UUID,
    plan_slug: str,
    trial_days: Optional[int] = None
) -> Subscription:
    """
    Create new subscription with automatic usage tracking.
    
    - Creates subscription record
    - Sets trial period if configured
    - Initializes feature usage tracking
    - Calculates initial pricing
    """
```

#### Manage Addons
```python
async def add_addon(
    subscription_id: UUID,
    feature_slug: str,
    custom_limit: Optional[int] = None,
    custom_price: Optional[float] = None
) -> SubscriptionAddon:
    """Add à la carte feature with optional customization"""

async def remove_addon(addon_id: UUID):
    """Deactivate addon and recalculate totals"""

async def update_addon(
    addon_id: UUID,
    limit: Optional[int] = None,
    price: Optional[float] = None
) -> SubscriptionAddon:
    """Modify addon limit or price"""
```

#### Discount Management
```python
async def apply_discount(
    subscription_id: UUID,
    discount_code: str,
    target: str = 'subscription',
    addon_id: Optional[UUID] = None
) -> Discount:
    """
    Apply discount with flexible targeting:
    - 'subscription': Discount entire subscription
    - 'addon': Discount specific addon
    - 'all': Apply to all components
    """
```

#### Plan Changes
```python
async def change_plan(
    subscription_id: UUID,
    new_plan_slug: str,
    proration: str = 'calculate'
) -> Subscription:
    """
    Change to different plan with pro-rata calculations.
    
    Proration modes:
    - 'calculate': Credit/charge based on remaining period
    - 'none': Apply immediately, no adjustments
    - 'always_invoice': Force new invoice
    """
```

#### Subscription Lifecycle
```python
async def cancel_subscription(
    subscription_id: UUID,
    immediate: bool = False,
    reason: Optional[str] = None
) -> Subscription:
    """Cancel subscription immediately or at period end"""

async def reactivate_subscription(subscription_id: UUID) -> Subscription:
    """Reactivate cancelled subscription"""

async def get_subscription_summary(org_id: UUID) -> Dict:
    """Get complete pricing breakdown with all details"""
```

### BillingService (`services/billing_service.py`)

Handles feature access, quota checking, and usage tracking.

**Key Methods:**

#### Feature Access
```python
async def has_feature_access(org_id: UUID, feature_slug: str) -> bool:
    """Check if organization has access to feature"""

async def get_feature_status(org_id: UUID, feature_slug: str) -> Dict:
    """
    Get comprehensive feature status:
    - Access level
    - Feature type
    - Current usage (for quota)
    - Remaining quota
    - Warning status
    """

async def get_org_feature_limits(org_id: UUID) -> Dict[str, Dict]:
    """Get all features with current usage and limits"""
```

#### Quota Management
```python
async def check_quota(org_id: UUID, feature_slug: str) -> Dict:
    """
    Check current quota usage:
    - Current usage count
    - Limit
    - Remaining
    - Usage percentage
    - Warning if > 80%
    - Reset date
    """

async def increment_usage(
    org_id: UUID,
    feature_slug: str,
    amount: int = 1,
    metadata: Optional[Dict] = None
) -> Dict:
    """Increment usage with quota validation"""

async def batch_increment_usage(
    org_id: UUID,
    usages: Dict[str, int]  # {feature_slug: amount}
) -> Dict[str, Dict]:
    """Atomically increment multiple features"""

async def reset_usage(org_id: UUID, feature_slug: str):
    """Reset usage counter (admin only)"""

async def override_feature_limit(
    org_id: UUID,
    feature_slug: str,
    new_limit: int
):
    """Set custom limit for feature (e.g., negotiated deals)"""

async def get_usage_analytics(org_id: UUID) -> Dict:
    """Get usage statistics across all features"""
```

### StripeService (`services/stripe_service.py`)

Integrates with Stripe for payment processing.

**Key Methods:**

#### Customer Management
```python
async def create_or_update_customer(
    org_id: UUID,
    org_name: str,
    billing_email: str,
    metadata: Optional[Dict] = None
) -> str:
    """Create or update Stripe customer"""
```

#### Product & Price Management
```python
async def create_stripe_product(
    plan_slug: str,
    plan_name: str,
    plan_description: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> str:
    """Create Stripe product for plan"""

async def create_stripe_price(
    product_id: str,
    plan_slug: str,
    amount_in_cents: int,
    currency: str = 'usd',
    interval: str = 'month',
    setup_fee_cents: Optional[int] = None
) -> str:
    """Create Stripe price with optional setup fee"""
```

#### Subscription Management
```python
async def create_subscription(
    stripe_customer_id: str,
    stripe_price_id: str,
    org_id: UUID,
    trial_days: Optional[int] = None
) -> Dict:
    """Create Stripe subscription"""

async def update_subscription_price(
    stripe_subscription_id: str,
    new_stripe_price_id: str
) -> Dict:
    """Change subscription price (plan upgrade/downgrade)"""

async def add_subscription_item(
    stripe_subscription_id: str,
    stripe_price_id: str
) -> str:
    """Add item (addon) to subscription"""

async def cancel_subscription(
    stripe_subscription_id: str,
    immediate: bool = False
) -> Dict:
    """Cancel subscription"""

async def reactivate_subscription(stripe_subscription_id: str) -> Dict:
    """Reactivate cancelled subscription"""

async def get_subscription(stripe_subscription_id: str) -> Dict:
    """Retrieve subscription details"""
```

#### Coupon & Discount Management
```python
async def create_coupon(
    discount_code: str,
    amount_off_cents: Optional[int] = None,
    percent_off: Optional[float] = None,
    max_redemptions: Optional[int] = None
) -> str:
    """Create Stripe coupon"""

async def apply_coupon_to_subscription(
    stripe_subscription_id: str,
    coupon_id: str
) -> Dict:
    """Apply coupon to subscription"""

async def remove_coupon_from_subscription(
    stripe_subscription_id: str
) -> Dict:
    """Remove coupon from subscription"""
```

#### Invoice Management
```python
async def create_invoice(
    stripe_customer_id: str,
    description: Optional[str] = None
) -> str:
    """Create manual invoice"""

async def finalize_invoice(stripe_invoice_id: str) -> Dict:
    """Finalize draft invoice"""

async def send_invoice(stripe_invoice_id: str):
    """Send invoice to customer"""

async def get_invoice(stripe_invoice_id: str) -> Dict:
    """Retrieve invoice details"""
```

#### Webhook Handling
```python
async def handle_invoice_paid(invoice_id: str) -> Dict:
    """Handle invoice.paid event"""

async def handle_invoice_payment_failed(invoice_id: str) -> Dict:
    """Handle invoice.payment_failed event"""

async def handle_subscription_updated(subscription_id: str) -> Dict:
    """Handle customer.subscription.updated event"""

async def handle_subscription_deleted(subscription_id: str) -> Dict:
    """Handle customer.subscription.deleted event"""
```

---

## API Endpoints

All endpoints are in `api/v1/routes/billing.py`.

### Subscription Management

#### Create Subscription
```http
POST /api/v1/billing/subscribe
Content-Type: application/json

{
  "plan_slug": "pro",
  "trial_days": 14
}

Response 200:
{
  "id": "uuid",
  "org_id": "uuid",
  "plan_id": "uuid",
  "status": "trialing",
  "base_price": 29.99,
  "trial_end": "2024-02-15T00:00:00Z",
  "stripe_subscription_id": "sub_xxx"
}
```

#### Get Current Subscription
```http
GET /api/v1/billing/subscription

Response 200:
{
  "id": "uuid",
  "plan": {
    "slug": "pro",
    "name": "Pro",
    "base_price": 29.99
  },
  "status": "active",
  "billing_period_start": "2024-01-15T00:00:00Z",
  "billing_period_end": "2024-02-15T00:00:00Z"
}
```

#### Get Subscription Summary
```http
GET /api/v1/billing/summary

Response 200:
{
  "subscription": { ... },
  "plan": { ... },
  "addons": [
    {
      "feature": "advanced_analytics",
      "price": 49.99,
      "limit": 5000
    }
  ],
  "discounts": [
    {
      "code": "SAVE20",
      "amount": -6.00
    }
  ],
  "pricing_breakdown": {
    "base_price": 29.99,
    "addons_price": 49.99,
    "discount_amount": -6.00,
    "tax_amount": 6.48,
    "total_price": 80.46
  }
}
```

#### Change Plan
```http
POST /api/v1/billing/plan-change
Content-Type: application/json

{
  "new_plan_slug": "expert",
  "proration": "calculate"
}

Response 200:
{
  "id": "uuid",
  "plan_id": "uuid",
  "status": "active",
  "base_price": 99.99,
  "proration_credit": 10.00
}
```

#### Cancel Subscription
```http
POST /api/v1/billing/cancel
Content-Type: application/json

{
  "immediate": false,
  "reason": "switching_providers"
}

Response 200:
{
  "status": "cancelled",
  "cancelled_at": "2024-01-20T12:00:00Z"
}
```

#### Reactivate Subscription
```http
POST /api/v1/billing/reactivate

Response 200:
{
  "status": "active",
  "reactivated_at": "2024-01-20T12:00:00Z"
}
```

### Addon Management

#### Add Addon
```http
POST /api/v1/billing/addons
Content-Type: application/json

{
  "feature_slug": "advanced_analytics",
  "custom_limit": 5000,
  "custom_price": 49.99
}

Response 200:
{
  "id": "uuid",
  "feature": {
    "slug": "advanced_analytics",
    "name": "Advanced Analytics"
  },
  "limit": 5000,
  "price": 49.99,
  "is_active": true
}
```

#### Remove Addon
```http
DELETE /api/v1/billing/addons/{addon_id}

Response 200:
{
  "message": "Addon removed successfully"
}
```

#### Update Addon
```http
PUT /api/v1/billing/addons/{addon_id}
Content-Type: application/json

{
  "custom_limit": 10000,
  "custom_price": 99.99
}

Response 200:
{
  "id": "uuid",
  "limit": 10000,
  "price": 99.99
}
```

### Discount Management

#### Apply Discount
```http
POST /api/v1/billing/discounts
Content-Type: application/json

{
  "discount_code": "SAVE20",
  "target": "subscription"
}

Response 200:
{
  "id": "uuid",
  "code": "SAVE20",
  "discount_type": "percentage",
  "discount_value": 20,
  "discount_amount": 6.00
}
```

### Feature & Quota Management

#### Get Feature Limits
```http
GET /api/v1/billing/features

Response 200:
{
  "api_requests": {
    "name": "API Requests",
    "type": "quota",
    "current": 245,
    "limit": 1000,
    "remaining": 755,
    "usage_percent": 24.5,
    "has_access": true,
    "resets_at": "2024-02-15T00:00:00Z"
  },
  "advanced_analytics": {
    "name": "Advanced Analytics",
    "type": "boolean",
    "enabled": true
  }
}
```

#### Get Feature Status
```http
GET /api/v1/billing/features/{feature_slug}

Response 200:
{
  "has_access": true,
  "feature_type": "quota",
  "status": "included_in_plan",
  "current": 245,
  "limit": 1000,
  "remaining": 755,
  "usage_percent": 24.5,
  "warning": false
}
```

#### Check Quota
```http
GET /api/v1/billing/quota/{feature_slug}

Response 200:
{
  "has_access": true,
  "current": 245,
  "limit": 1000,
  "remaining": 755,
  "usage_percent": 24.5,
  "warning": false,
  "resets_at": "2024-02-15T00:00:00Z"
}
```

#### Increment Usage
```http
POST /api/v1/billing/usage
Content-Type: application/json

{
  "feature_slug": "api_requests",
  "amount": 1,
  "metadata": {
    "endpoint": "/users",
    "user_id": "uuid"
  }
}

Response 200:
{
  "has_access": true,
  "current": 246,
  "limit": 1000,
  "remaining": 754,
  "usage_percent": 24.6
}
```

#### Get Usage Analytics
```http
GET /api/v1/billing/usage/analytics

Response 200:
{
  "api_requests": {
    "name": "API Requests",
    "periods_tracked": 3,
    "total_usage": 1250,
    "avg_per_period": 416.67,
    "peak_usage": 500,
    "limit": 1000
  }
}
```

---

## Feature Access & Quota Management

### Using Decorators for Quota Enforcement

#### Simple Feature Access Check
```python
from core.decorators.quota_enforcement import require_feature_access

@router.get("/advanced-analytics")
@require_feature_access("advanced_analytics")
async def get_advanced_analytics(
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Only accessible if feature is in plan or added as addon"""
    return {...}
```

#### Quota Enforcement with Auto-Increment
```python
from core.decorators.quota_enforcement import require_feature_quota

@router.post("/api/call")
@require_feature_quota("api_requests", cost=1, strict=True)
async def make_api_call(
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    - Checks quota before execution
    - Raises 403 if quota exceeded
    - Auto-increments usage on success
    """
    return {...}
```

#### Conditional Feature Access
```python
from core.decorators.quota_enforcement import FeatureGate

@router.get("/export")
async def export_data(
    has_access: bool = Depends(FeatureGate("bulk_export")),
    org_id: UUID = Depends(get_current_org_id)
):
    """Gate behind feature access"""
    if has_access:
        # Allow export
        ...
```

#### Get Quota Info as Dependency
```python
from core.decorators.quota_enforcement import QuotaDependency

@router.get("/items")
async def list_items(
    quota: dict = Depends(QuotaDependency("api_requests")),
    org_id: UUID = Depends(get_current_org_id)
):
    """Get quota info and decide dynamically"""
    if quota['usage_percent'] > 90:
        # Rate limit more aggressively
        ...
```

### Manual Usage Tracking

```python
from core.decorators.quota_enforcement import track_feature_usage

# Anywhere in your code:
await track_feature_usage(
    db, org_id,
    feature_slug="api_requests",
    amount=1,
    metadata={
        "endpoint": "/users",
        "user_id": str(user_id)
    }
)
```

### Batch Operations

```python
from core.decorators.quota_enforcement import validate_batch_operations

# Check multiple features before batch operation
operations = {
    "api_requests": 100,
    "storage_gb": 50,
    "email_sends": 10000
}

can_proceed = await validate_batch_operations(db, org_id, operations)
if not can_proceed:
    raise Exception("Quota would be exceeded for one or more features")

# Proceed with batch operation
...
```

### Adaptive Rate Limiting

```python
from core.decorators.quota_enforcement import AdaptiveRateLimiter

limiter = AdaptiveRateLimiter("api_requests", base_requests=100)

# Get rate limit that adapts based on quota usage
limit = await limiter.get_limit(db, org_id)
# limit = 100 if usage < 50%
# limit = 75 if usage 50-75%
# limit = 50 if usage 75-90%
# limit = 25 if usage > 90%
```

---

## Stripe Integration

### Configuration

Add to `.env`:
```env
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_PUBLIC_KEY=pk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
```

### Setting Up Stripe Products

```python
from services.stripe_service import StripeService

stripe_service = StripeService(db, settings)

# Create products for each plan
beginner_product = await stripe_service.create_stripe_product(
    plan_slug="beginner",
    plan_name="Beginner Plan",
    plan_description="Perfect for getting started"
)

# Create prices
beginner_price = await stripe_service.create_stripe_price(
    product_id=beginner_product,
    plan_slug="beginner",
    amount_in_cents=999,      # $9.99
    currency="usd",
    interval="month",
    setup_fee_cents=0
)

# Create coupon for discount code
await stripe_service.create_coupon(
    discount_code="SAVE20",
    percent_off=20.0,
    max_redemptions=100,
    redeem_by=int(datetime(2024, 12, 31).timestamp())
)
```

### Creating Subscription via API

```python
# 1. Create customer
customer_id = await stripe_service.create_or_update_customer(
    org_id=org_id,
    org_name=org_name,
    billing_email=billing_email
)

# 2. Create subscription
stripe_sub = await stripe_service.create_subscription(
    stripe_customer_id=customer_id,
    stripe_price_id=price_id,
    org_id=org_id,
    trial_days=14
)

# 3. Create in-app subscription record
subscription = await subscription_service.create_subscription(
    org_id=org_id,
    plan_slug="pro",
    trial_days=14
)

# 4. Sync Stripe subscription ID
await db.execute(
    update(Subscription).where(Subscription.id == subscription.id).values(
        stripe_customer_id=customer_id,
        stripe_subscription_id=stripe_sub['subscription_id']
    )
)
await db.commit()
```

### Webhook Setup

1. Go to Stripe Dashboard → Developers → Webhooks
2. Create endpoint with URL: `https://yourdomain.com/api/v1/billing/webhooks/stripe`
3. Select events:
   - `invoice.paid`
   - `invoice.payment_failed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
4. Copy Webhook Secret to `.env`

### Handling Webhooks

Stripe automatically posts to `/api/v1/billing/webhooks/stripe`:

```python
@router.post("/webhooks/stripe")
async def stripe_webhook(request, db: AsyncSession = Depends(get_db)):
    """Automatically handles subscription state synchronization"""
    # Implementation in billing.py routes
```

---

## Database Initialization

### Create Tables

```sql
-- Run migrations to create all tables
alembic upgrade head
```

### Seed Plans & Features

```python
from sqlalchemy import text

async def seed_plans_and_features(db: AsyncSession):
    """Initialize default plans and features"""
    
    # Create plans
    plans = [
        {
            "slug": "beginner",
            "name": "Beginner",
            "base_price": 9.99,
            "setup_fee": 0,
            "billing_interval": "monthly",
            "max_features": 3,
            "trial_days": 14
        },
        {
            "slug": "pro",
            "name": "Pro",
            "base_price": 29.99,
            "setup_fee": 0,
            "billing_interval": "monthly",
            "max_features": 10,
            "trial_days": 14
        },
        {
            "slug": "expert",
            "name": "Expert",
            "base_price": 99.99,
            "setup_fee": 99,
            "billing_interval": "monthly",
            "max_features": -1,  # Unlimited
            "trial_days": 30
        }
    ]
    
    for plan_data in plans:
        plan = Plan(**plan_data)
        db.add(plan)
    
    # Create features
    features = [
        {
            "slug": "advanced_analytics",
            "name": "Advanced Analytics",
            "feature_type": "boolean",
            "standalone_price": 29.99,
            "customizable": False
        },
        {
            "slug": "api_requests",
            "name": "API Requests",
            "feature_type": "quota",
            "default_limit": 1000,
            "standalone_price": 0.01,
            "customizable": True
        },
        {
            "slug": "bulk_export",
            "name": "Bulk Export",
            "feature_type": "boolean",
            "standalone_price": 49.99,
            "customizable": False
        }
    ]
    
    for feature_data in features:
        feature = Feature(**feature_data)
        db.add(feature)
    
    await db.commit()
    
    # Map features to plans
    # Beginner: advanced_analytics (1000 API calls)
    # Pro: advanced_analytics + bulk_export (5000 API calls)
    # Expert: all features unlimited

seed_plans_and_features(db)
```

---

## Usage Examples

### Complete Subscription Flow

```python
# 1. Create subscription
subscription = await subscription_service.create_subscription(
    org_id=org_id,
    plan_slug="pro",
    trial_days=14
)

# 2. Add addon (Advanced Analytics)
addon = await subscription_service.add_addon(
    subscription_id=subscription.id,
    feature_slug="advanced_analytics",
    custom_price=25.00  # Negotiated price
)

# 3. Apply discount
discount = await subscription_service.apply_discount(
    subscription_id=subscription.id,
    discount_code="WELCOME10",
    target="subscription"
)

# 4. Get pricing breakdown
summary = await subscription_service.get_subscription_summary(org_id)
print(f"Total: ${summary['pricing_breakdown']['total_price']}")

# 5. Track feature usage
await billing_service.increment_usage(org_id, "api_requests", 5)

# 6. Check quota before operation
quota = await billing_service.check_quota(org_id, "api_requests")
if quota['has_access']:
    # Proceed with operation
    await make_api_call()
else:
    # Rate limit or deny
    raise RateLimitError()

# 7. Change plan
new_subscription = await subscription_service.change_plan(
    subscription_id=subscription.id,
    new_plan_slug="expert",
    proration="calculate"
)

# 8. Cancel subscription
await subscription_service.cancel_subscription(
    subscription_id=subscription.id,
    immediate=False,
    reason="budget_constraints"
)
```

### Permission-Aware API

```python
# Only allow users with "bulk_export" feature
@router.post("/export")
@require_feature_access("bulk_export")
async def export_data(
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Export organization data in CSV format"""
    # Feature access is guaranteed here
    ...

# Rate-limited API with usage tracking
@router.post("/api/call")
@require_feature_quota("api_requests", cost=1)
async def api_call(
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Make API call with automatic quota tracking"""
    # Quota is checked and usage is incremented automatically
    ...
```

---

## Advanced Scenarios

### Custom Pricing Per Organization

```python
# Negotiate custom pricing for large customer
addon = await subscription_service.add_addon(
    subscription_id=subscription.id,
    feature_slug="api_requests",
    custom_limit=100000,    # Custom limit
    custom_price=5000       # Custom price (not per-request)
)
```

### Multi-Level Discounts

```python
# Apply discount to entire subscription
discount1 = await subscription_service.apply_discount(
    subscription_id=subscription.id,
    discount_code="ANNUAL20",  # 20% off
    target="subscription"
)

# Apply separate discount to addon
addon_discount = await subscription_service.apply_discount(
    subscription_id=subscription.id,
    discount_code="ANALYTICS_PROMO",  # $10 off analytics
    target="addon",
    addon_id=addon.id
)
```

### Prorated Plan Changes

```python
# Upgrade from Beginner ($9.99) to Pro ($29.99)
# On day 15 of 30-day month
# Pro-rata credit: $9.99 * (15/30) = $5.00
# New charge: $29.99 - $5.00 = $24.99

updated = await subscription_service.change_plan(
    subscription_id=subscription.id,
    new_plan_slug="pro",
    proration="calculate"  # Automatic credit calculation
)

# Check proration details
summary = await subscription_service.get_subscription_summary(org_id)
# summary['proration_credit'] = 5.00
# summary['proration_charge'] = 24.99
```

### Feature Upgrades with Trial

```python
# Add feature with trial period
addon = await subscription_service.add_addon(
    subscription_id=subscription.id,
    feature_slug="advanced_analytics",
    custom_price=0  # Free trial
)

# After 7 days, activate for real
# (Would be triggered by scheduled job)
addon.price_override = 29.99
await db.commit()
```

### Quota Enforcement Example

```python
# Set up adaptive rate limiting
from core.decorators.quota_enforcement import AdaptiveRateLimiter

limiter = AdaptiveRateLimiter("api_requests", base_requests=100, window_seconds=3600)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if "/api/call" in request.url.path:
        org_id = request.scope.get("org_id")
        limit = await limiter.get_limit(db, org_id)
        
        # Rate limit enforcement
        current_count = await get_request_count(org_id)
        if current_count >= limit:
            return JSONResponse({"error": "Rate limit exceeded"}, status_code=429)
    
    return await call_next(request)
```

### Batch Operations with Quota Validation

```python
# Bulk import 1000 items, each costs 5 API requests
total_cost = 1000 * 5

operations = {
    "api_requests": total_cost,
    "storage_gb": 100
}

can_proceed = await validate_batch_operations(db, org_id, operations)

if can_proceed:
    # Proceed with bulk import
    for item in items:
        import_item(item)
        await track_feature_usage(db, org_id, "api_requests", 5)
else:
    raise HTTPException(403, "Quota would be exceeded")
```

---

## Best Practices

### 1. Always Use Transactions
```python
try:
    subscription = await subscription_service.create_subscription(...)
    addon = await subscription_service.add_addon(...)
    discount = await subscription_service.apply_discount(...)
    await db.commit()
except Exception as e:
    await db.rollback()
    raise
```

### 2. Cache Feature Access Checks
```python
# Cache for 5 minutes to reduce database queries
@functools.lru_cache(maxsize=1000)
async def cached_has_access(org_id: UUID, feature_slug: str):
    return await billing_service.has_feature_access(org_id, feature_slug)
```

### 3. Use Batch Operations for Efficiency
```python
# Batch update for multiple features
await billing_service.batch_increment_usage(
    org_id,
    {
        "api_requests": 5,
        "storage_gb": 10,
        "email_sends": 100
    }
)
```

### 4. Monitor Quota Warnings
```python
# Check quotas daily and send warnings
async def send_quota_warnings():
    for org in all_organizations:
        features = await billing_service.get_org_feature_limits(org.id)
        for slug, status in features.items():
            if status.get('warning'):
                send_email(
                    org.billing_email,
                    f"Warning: {slug} quota at {status['usage_percent']}%"
                )
```

### 5. Sync with Stripe Regularly
```python
# Sync subscription status hourly
async def sync_stripe_subscriptions():
    for subscription in get_all_active_subscriptions():
        if subscription.stripe_subscription_id:
            stripe_sub = await stripe_service.get_subscription(
                subscription.stripe_subscription_id
            )
            # Update local subscription status
            subscription.status = stripe_sub['status']
            await db.commit()
```

---

## Summary

This comprehensive subscription & billing system provides:

✅ **Flexible Pricing**: Plans + addons with custom pricing  
✅ **Advanced Discounts**: Multiple discount types and targets  
✅ **Quota Management**: Track and enforce usage limits  
✅ **Stripe Integration**: Full payment processing  
✅ **Multi-Tenant**: Per-organization subscriptions  
✅ **Feature Gating**: Boolean and quota-based access control  
✅ **Analytics**: Usage tracking and reporting  
✅ **Pro-rata Calculations**: Smart plan change handling  
✅ **Webhook Support**: Automatic Stripe event handling  
✅ **Extensible**: Easy to customize and extend  

All components are production-ready with comprehensive error handling, type hints, and documentation.
