"""
Quota Enforcement Decorators & Middleware
Provides feature access and quota checking for API endpoints
"""

from functools import wraps
from typing import Optional, Callable, Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_current_org_id
from services.billing_service import BillingService
from utils.response import HttpError


def require_feature_access(feature_slug: str):
    """
    Decorator to require feature access before executing endpoint.
    
    Usage:
        @router.get("/analytics")
        @require_feature_access("advanced_analytics")
        async def get_analytics(org_id: UUID = Depends(get_current_org_id)):
            ...
    """
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Extract dependencies from kwargs
            db: AsyncSession = kwargs.get('db')
            org_id: UUID = kwargs.get('org_id')
            
            if not db or not org_id:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Missing required dependencies"
                )
            
            # Check feature access
            service = BillingService(db)
            has_access = await service.has_feature_access(org_id, feature_slug)
            
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Feature '{feature_slug}' not available in current plan. Please upgrade or add this feature."
                )
            
            # Call original function
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_feature_quota(
    feature_slug: str,
    cost: int = 1,
    strict: bool = True
):
    """
    Decorator to enforce quota limits before executing endpoint.
    
    Args:
        feature_slug: Feature to check quota for
        cost: Usage cost of this operation (default 1)
        strict: If True, increment usage on success. If False, requires manual increment.
    
    Usage:
        @router.post("/api/call")
        @require_feature_quota("api_requests", cost=1)
        async def make_api_call(org_id: UUID = Depends(get_current_org_id)):
            ...
    """
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Extract dependencies
            db: AsyncSession = kwargs.get('db')
            org_id: UUID = kwargs.get('org_id')
            
            if not db or not org_id:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Missing required dependencies"
                )
            
            service = BillingService(db)
            
            # Check quota
            try:
                quota = await service.check_quota(org_id, feature_slug)
                
                if not quota.get('has_access'):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Quota limit reached for {feature_slug}. {quota.get('current')}/{quota.get('limit')} used."
                    )
                
                if quota.get('remaining') and quota['remaining'] < cost:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Insufficient quota. Available: {quota['remaining']}, Required: {cost}"
                    )
                
            except HttpError as e:
                raise HTTPException(status_code=e.status_code, detail=e.message)
            
            # Call original function
            result = await func(*args, **kwargs)
            
            # Increment usage if strict mode
            if strict:
                try:
                    await service.increment_usage(org_id, feature_slug, cost)
                except HttpError as e:
                    # Log but don't fail - feature already executed
                    print(f"Warning: Failed to increment usage for {feature_slug}: {e.message}")
            
            return result
        
        return wrapper
    return decorator


class QuotaMiddleware:
    """
    Middleware for automatic quota tracking across the application.
    Can be configured to track specific endpoints.
    """
    
    def __init__(self, app, tracking_config: Optional[dict] = None):
        """
        Args:
            app: FastAPI application
            tracking_config: Dict mapping endpoint patterns to quota config
                {
                    "/api/v1/items/{id}": {
                        "feature": "api_requests",
                        "cost": 1,
                        "methods": ["GET", "POST"]
                    }
                }
        """
        self.app = app
        self.tracking_config = tracking_config or {}
    
    async def __call__(self, request, call_next):
        # For now, just pass through
        # In production, could implement automatic tracking
        response = await call_next(request)
        return response


class FeatureGate:
    """
    Simple feature gate for boolean feature access.
    Raises exception if feature not available.
    """
    
    def __init__(self, feature_slug: str):
        self.feature_slug = feature_slug
    
    async def __call__(
        self,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db)
    ) -> bool:
        """
        Can be used as a dependency to gate features.
        
        Usage:
            @router.get("/advanced")
            async def advanced_feature(
                has_access: bool = Depends(FeatureGate("advanced_analytics"))
            ):
                ...
        """
        
        service = BillingService(db)
        has_access = await service.has_feature_access(org_id, self.feature_slug)
        
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature '{self.feature_slug}' not available. Please upgrade your plan."
            )
        
        return True


class QuotaDependency:
    """
    Dependency for getting current quota status.
    Can be used to conditionally execute features.
    
    Usage:
        @router.get("/items")
        async def get_items(
            quota: dict = Depends(QuotaDependency("api_requests"))
        ):
            if not quota['has_access']:
                raise HTTPException(403, "Quota exceeded")
            ...
    """
    
    def __init__(self, feature_slug: str):
        self.feature_slug = feature_slug
    
    async def __call__(
        self,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db)
    ) -> dict:
        """Returns quota status dict"""
        
        service = BillingService(db)
        return await service.check_quota(org_id, self.feature_slug)


# ===================== USAGE TRACKING HELPERS =====================

async def track_feature_usage(
    db: AsyncSession,
    org_id: UUID,
    feature_slug: str,
    amount: int = 1,
    metadata: Optional[dict] = None
):
    """
    Helper function to track feature usage.
    Can be called from anywhere in the codebase.
    
    Usage:
        await track_feature_usage(
            db, org_id, "api_requests", 
            amount=1, 
            metadata={"endpoint": "/items"}
        )
    """
    
    service = BillingService(db)
    try:
        await service.increment_usage(org_id, feature_slug, amount, metadata)
    except HttpError as e:
        # Could log this or handle differently based on app needs
        raise


async def check_feature_access(
    db: AsyncSession,
    org_id: UUID,
    feature_slug: str
) -> bool:
    """
    Helper to check if organization has feature access.
    
    Usage:
        can_use = await check_feature_access(db, org_id, "advanced_analytics")
        if not can_use:
            # Handle missing feature
    """
    
    service = BillingService(db)
    return await service.has_feature_access(org_id, feature_slug)


async def get_quota_status(
    db: AsyncSession,
    org_id: UUID,
    feature_slug: str
) -> dict:
    """
    Helper to get current quota status for a feature.
    
    Returns:
        {
            'has_access': bool,
            'current': int,
            'limit': int,
            'remaining': int,
            'warning': bool,
            ...
        }
    """
    
    service = BillingService(db)
    return await service.check_quota(org_id, feature_slug)


# ===================== BATCH QUOTA CHECKING =====================

async def validate_batch_operations(
    db: AsyncSession,
    org_id: UUID,
    operations: dict  # {feature_slug: count}
) -> bool:
    """
    Validate that multiple operations can be performed.
    Returns False if any quota would be exceeded.
    
    Usage:
        operations = {
            "api_requests": 10,
            "storage_gb": 5
        }
        
        can_proceed = await validate_batch_operations(db, org_id, operations)
        if not can_proceed:
            raise Exception("Quota would be exceeded")
    """
    
    service = BillingService(db)
    
    for feature_slug, amount in operations.items():
        quota = await service.check_quota(org_id, feature_slug)
        
        if not quota.get('has_access'):
            return False
        
        if quota.get('remaining') and quota['remaining'] < amount:
            return False
    
    return True


# ===================== ADAPTIVE RATE LIMITING =====================

class AdaptiveRateLimiter:
    """
    Rate limiter that adapts based on quota usage.
    Tightens limits as quota approaches limit.
    """
    
    def __init__(
        self,
        feature_slug: str,
        base_requests: int = 100,
        window_seconds: int = 3600
    ):
        """
        Args:
            feature_slug: Feature to rate limit
            base_requests: Base requests per window
            window_seconds: Time window in seconds
        """
        self.feature_slug = feature_slug
        self.base_requests = base_requests
        self.window_seconds = window_seconds
    
    async def get_limit(
        self,
        db: AsyncSession,
        org_id: UUID
    ) -> int:
        """
        Get current rate limit based on quota usage.
        Reduces limit as quota approaches limit.
        """
        
        service = BillingService(db)
        quota = await service.check_quota(org_id, self.feature_slug)
        
        if not quota.get('has_access'):
            return 0
        
        if quota.get('unlimited'):
            return self.base_requests
        
        # Adaptive: reduce limit as quota fills
        usage_percent = quota.get('usage_percent', 0)
        
        if usage_percent < 50:
            return self.base_requests
        elif usage_percent < 75:
            return int(self.base_requests * 0.75)
        elif usage_percent < 90:
            return int(self.base_requests * 0.5)
        else:
            return int(self.base_requests * 0.25)
