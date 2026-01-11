"""
Billing & Subscription API Routes
Handles subscription management, addons, discounts, and billing operations
Note: Payment processing endpoints are deferred. See TODO comments for implementation details.
"""

from datetime import datetime
from typing import Optional, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_current_user, get_tenant_id
from core.security import get_current_org_id
from services.subscription_service import SubscriptionService
from services.billing_service import BillingService
# TODO: Stripe integration will be implemented later
# from services.stripe_service import StripeService
from models.user import User
from utils.response import HttpError, success_response, error_response
from core.config import settings


# ===================== SCHEMAS =====================

class CreateSubscriptionRequest(BaseModel):
    plan_slug: str = Field(..., description="Plan slug (e.g., 'pro')")
    trial_days: Optional[int] = Field(None, description="Number of trial days")
    
    class Config:
        examples = [
            {
                "plan_slug": "pro",
                "trial_days": 14
            }
        ]


class AddAddonRequest(BaseModel):
    feature_slug: str = Field(..., description="Feature slug")
    custom_limit: Optional[int] = Field(None, description="Override default limit")
    custom_price: Optional[float] = Field(None, description="Override default price")
    
    class Config:
        examples = [
            {
                "feature_slug": "advanced_analytics",
                "custom_limit": 5000,
                "custom_price": 49.99
            }
        ]


class ApplyDiscountRequest(BaseModel):
    discount_code: str = Field(..., description="Discount code")
    target: Optional[str] = Field("subscription", description="Apply to 'subscription', 'addon', or 'all'")
    addon_id: Optional[UUID] = Field(None, description="Addon ID if target is 'addon'")
    
    class Config:
        examples = [
            {
                "discount_code": "SAVE20",
                "target": "subscription"
            }
        ]


class ChangePlanRequest(BaseModel):
    new_plan_slug: str = Field(..., description="Target plan slug")
    proration: str = Field("calculate", description="'calculate', 'none', or 'always_invoice'")
    
    class Config:
        examples = [
            {
                "new_plan_slug": "expert",
                "proration": "calculate"
            }
        ]


class CancelSubscriptionRequest(BaseModel):
    immediate: bool = Field(False, description="Cancel immediately or at period end")
    reason: Optional[str] = Field(None, description="Cancellation reason")
    
    class Config:
        examples = [
            {
                "immediate": False,
                "reason": "switching_providers"
            }
        ]


class IncrementUsageRequest(BaseModel):
    feature_slug: str = Field(..., description="Feature slug")
    amount: int = Field(1, ge=1, description="Amount to increment")
    metadata: Optional[Dict] = Field(None, description="Additional metadata")
    
    class Config:
        examples = [
            {
                "feature_slug": "api_requests",
                "amount": 5,
                "metadata": {"endpoint": "/users"}
            }
        ]


# ===================== ROUTER =====================

router = APIRouter(
    prefix="/api/v1/billing",
    tags=["billing"],
    dependencies=[Depends(get_current_user)]
)


# ===================== SUBSCRIPTION MANAGEMENT =====================

@router.post("/subscribe")
async def create_subscription(
    request: CreateSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Create subscription for organization"""
    
    try:
        service = SubscriptionService(db)
        subscription = await service.create_subscription(
            org_id=org_id,
            plan_slug=request.plan_slug,
            trial_days=request.trial_days
        )
        
        return success_response(
            data=subscription.to_dict(),
            message="Subscription created successfully"
        )
    except HttpError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create subscription"
        )


@router.get("/subscription")
async def get_subscription(
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Get current subscription for organization"""
    
    try:
        service = SubscriptionService(db)
        subscription = await service.get_org_subscription(org_id)
        
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription found"
            )
        
        return success_response(
            data=subscription.to_dict(),
            message="Subscription retrieved"
        )
    except HttpError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/summary")
async def get_subscription_summary(
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Get subscription pricing breakdown and details"""
    
    try:
        service = SubscriptionService(db)
        summary = await service.get_subscription_summary(org_id)
        
        return success_response(
            data=summary,
            message="Subscription summary retrieved"
        )
    except HttpError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/plan-change")
async def change_plan(
    request: ChangePlanRequest,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Change to a different subscription plan"""
    
    try:
        # Get current subscription
        service = SubscriptionService(db)
        subscription = await service.get_org_subscription(org_id)
        
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription found"
            )
        
        # Change plan
        updated = await service.change_plan(
            subscription_id=subscription.id,
            new_plan_slug=request.new_plan_slug,
            proration=request.proration
        )
        
        return success_response(
            data=updated.to_dict(),
            message=f"Plan changed to {request.new_plan_slug}"
        )
    except HttpError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/cancel")
async def cancel_subscription(
    request: CancelSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Cancel subscription"""
    
    try:
        service = SubscriptionService(db)
        subscription = await service.get_org_subscription(org_id)
        
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription found"
            )
        
        cancelled = await service.cancel_subscription(
            subscription_id=subscription.id,
            immediate=request.immediate,
            reason=request.reason
        )
        
        return success_response(
            data=cancelled.to_dict(),
            message="Subscription cancelled"
        )
    except HttpError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/reactivate")
async def reactivate_subscription(
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Reactivate cancelled subscription"""
    
    try:
        service = SubscriptionService(db)
        
        # Find cancelled subscription
        subscription = await service.get_org_subscription(
            org_id,
            include_cancelled=True
        )
        
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No subscription found"
            )
        
        reactivated = await service.reactivate_subscription(subscription.id)
        
        return success_response(
            data=reactivated.to_dict(),
            message="Subscription reactivated"
        )
    except HttpError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ===================== ADDON MANAGEMENT =====================

@router.post("/addons")
async def add_addon(
    request: AddAddonRequest,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Add à la carte feature addon to subscription"""
    
    try:
        service = SubscriptionService(db)
        subscription = await service.get_org_subscription(org_id)
        
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription found"
            )
        
        addon = await service.add_addon(
            subscription_id=subscription.id,
            feature_slug=request.feature_slug,
            custom_limit=request.custom_limit,
            custom_price=request.custom_price
        )
        
        return success_response(
            data=addon.to_dict(),
            message="Addon added successfully"
        )
    except HttpError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete("/addons/{addon_id}")
async def remove_addon(
    addon_id: UUID,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Remove addon from subscription"""
    
    try:
        service = SubscriptionService(db)
        await service.remove_addon(addon_id)
        
        return success_response(
            message="Addon removed successfully"
        )
    except HttpError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.put("/addons/{addon_id}")
async def update_addon(
    addon_id: UUID,
    request: AddAddonRequest,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Update addon limit or price"""
    
    try:
        service = SubscriptionService(db)
        addon = await service.update_addon(
            addon_id=addon_id,
            limit=request.custom_limit,
            price=request.custom_price
        )
        
        return success_response(
            data=addon.to_dict(),
            message="Addon updated successfully"
        )
    except HttpError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ===================== DISCOUNT MANAGEMENT =====================

@router.post("/discounts")
async def apply_discount(
    request: ApplyDiscountRequest,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Apply discount code to subscription"""
    
    try:
        service = SubscriptionService(db)
        subscription = await service.get_org_subscription(org_id)
        
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription found"
            )
        
        discount = await service.apply_discount(
            subscription_id=subscription.id,
            discount_code=request.discount_code,
            target=request.target,
            addon_id=request.addon_id
        )
        
        return success_response(
            data=discount.to_dict(),
            message="Discount applied successfully"
        )
    except HttpError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ===================== FEATURE & QUOTA MANAGEMENT =====================

@router.get("/features")
async def get_feature_limits(
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Get all feature limits and usage for organization"""
    
    try:
        service = BillingService(db)
        features = await service.get_org_feature_limits(org_id)
        
        return success_response(
            data=features,
            message="Feature limits retrieved"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve feature limits"
        )


@router.get("/features/{feature_slug}")
async def get_feature_status(
    feature_slug: str,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Get status and quota for specific feature"""
    
    try:
        service = BillingService(db)
        status_data = await service.get_feature_status(org_id, feature_slug)
        
        return success_response(
            data=status_data,
            message="Feature status retrieved"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve feature status"
        )


@router.get("/quota/{feature_slug}")
async def check_quota(
    feature_slug: str,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Check current quota usage for feature"""
    
    try:
        service = BillingService(db)
        quota = await service.check_quota(org_id, feature_slug)
        
        return success_response(
            data=quota,
            message="Quota information retrieved"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check quota"
        )


@router.post("/usage")
async def increment_usage(
    request: IncrementUsageRequest,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Increment usage for quota-based feature"""
    
    try:
        service = BillingService(db)
        quota = await service.increment_usage(
            org_id=org_id,
            feature_slug=request.feature_slug,
            amount=request.amount,
            metadata=request.metadata
        )
        
        return success_response(
            data=quota,
            message="Usage incremented successfully"
        )
    except HttpError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/usage/analytics")
async def get_usage_analytics(
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Get usage analytics across all features"""
    
    try:
        service = BillingService(db)
        analytics = await service.get_usage_analytics(org_id)
        
        return success_response(
            data=analytics,
            message="Usage analytics retrieved"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve usage analytics"
        )


# ===================== WEBHOOK ENDPOINTS =====================

# TODO: Implement Stripe webhook endpoint for payment processing
# This endpoint will handle Stripe events for:
# - invoice.paid: Mark subscription as paid
# - invoice.payment_failed: Handle failed payments
# - customer.subscription.updated: Sync subscription changes
# - customer.subscription.deleted: Handle subscription cancellations
#
# @router.post("/webhooks/stripe")
# async def stripe_webhook(
#     request,
#     db: AsyncSession = Depends(get_db)
# ):
#     """Handle Stripe webhook events"""
#     
#     try:
#         # Get raw body and signature
#         payload = await request.body()
#         sig_header = request.headers.get("stripe-signature")
#         
#         if not sig_header:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Missing stripe-signature header"
#             )
#         
#         # Construct event
#         service = StripeService(db, settings)
#         event = service.construct_webhook_event(payload, sig_header)
#         
#         # Handle event
#         event_type = event['type']
#         event_data = event['data']['object']
#         
#         if event_type == 'invoice.paid':
#             result = await service.handle_invoice_paid(event_data['id'])
#         
#         elif event_type == 'invoice.payment_failed':
#             result = await service.handle_invoice_payment_failed(event_data['id'])
#         
#         elif event_type == 'customer.subscription.updated':
#             result = await service.handle_subscription_updated(event_data['id'])
#         
#         elif event_type == 'customer.subscription.deleted':
#             result = await service.handle_subscription_deleted(event_data['id'])
#         
#         else:
#             # Unknown event, log and continue
#             result = {'event': event_type, 'status': 'ignored'}
#         
#         return success_response(data=result, message="Webhook processed")
#     
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Failed to process webhook"
#         )
