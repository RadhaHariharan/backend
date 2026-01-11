from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import contextvars
from typing import List, Optional
from sqlalchemy import select, text
import uuid

from core.database import SessionLocal
from models.families import Organization
from core.middleware.auth_middleware import accessTokenData

# Context variable to hold current organization
currentOrg: contextvars.ContextVar[Organization] = contextvars.ContextVar("currentOrg", default=None)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware to:
    1. Extract orgId from token (set by AuthMiddleware)
    2. Fetch organization from public schema
    3. Set currentOrg context
    4. Set search_path for tenant schema
    
    This runs AFTER AuthMiddleware
    """

    def __init__(self, app, public_routes: List[str] = None):
        super().__init__(app)
        self.public_routes = public_routes or []

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # Skip for public routes
        if any(path.startswith(route) for route in self.public_routes):
            return await call_next(request)
        
        # Try to get token data from context
        token_data = accessTokenData.get()
        
        if not token_data:
            # No token, skip tenant setup
            return await call_next(request)
        
        # Extract orgId from token
        org_id = token_data.get("orgId")
        
        if org_id:
            try:
                # Fetch organization from public schema
                async with SessionLocal() as session:
                    await session.execute(text("SET search_path TO public"))
                    
                    result = await session.execute(
                        select(Organization).where(
                            Organization.id == uuid.UUID(org_id)
                        )
                    )
                    org = result.scalar_one_or_none()
                    
                    if org and org.is_active:
                        # Set organization in context
                        currentOrg.set(org)
            except Exception:
                # Silently continue if org lookup fails
                pass
        
        response = await call_next(request)
        return response
