from typing import AsyncGenerator, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from core.database import SessionLocal
from core.middleware.tenant_middleware import currentOrg
from utils.response import HttpError


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session with org schema set (REQUIRES orgId in token)
    Use this for tenant-specific operations
    """
    org = currentOrg.get()
    
    if not org:
        raise HttpError(400, "Organization context required", "ORG_CONTEXT_MISSING")
    
    schema_name = org.schema_name
    
    async with SessionLocal() as session:
        # Set search_path to org schema, then public
        await session.execute(text(f'SET search_path TO "{schema_name}", public'))
        try:
            yield session
        finally:
            await session.close()


async def get_public_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session for public schema only
    Use this for user management, org management, etc.
    """
    async with SessionLocal() as session:
        await session.execute(text("SET search_path TO public"))
        try:
            yield session
        finally:
            await session.close()


async def get_dual_db() -> AsyncGenerator[Tuple[AsyncSession, Optional[AsyncSession]], None]:
    """
    Get both public and tenant sessions
    Use this when you need to query both schemas
    
    Returns:
        (public_session, tenant_session or None)
    """
    org = currentOrg.get()
    
    async with SessionLocal() as public_session:
        await public_session.execute(text("SET search_path TO public"))
        
        tenant_session = None
        if org:
            tenant_session = SessionLocal()
            await tenant_session.execute(text(f'SET search_path TO "{org.schema_name}", public'))
        
        try:
            yield (public_session, tenant_session)
        finally:
            await public_session.close()
            if tenant_session:
                await tenant_session.close()