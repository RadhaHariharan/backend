import uuid
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.org_user import OrgUser


class OrgUserRepository:
    """
    OrgUser repository - operates on TENANT schema
    Assumes session already has correct search_path set
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user_id(self, user_id: str) -> Optional[OrgUser]:
        """Get org user by user_id (from public.users)"""
        result = await self.db.execute(
            select(OrgUser).where(OrgUser.user_id == uuid.UUID(user_id))
        )
        return result.scalar_one_or_none()
    
    async def get_by_email(self, email: str) -> Optional[OrgUser]:
        """Get org user by email"""
        result = await self.db.execute(
            select(OrgUser).where(OrgUser.email == email)
        )
        return result.scalar_one_or_none()
    
    async def create(self, org_user: OrgUser) -> OrgUser:
        """Create new org user (add user to this org)"""
        self.db.add(org_user)
        await self.db.commit()
        await self.db.refresh(org_user)
        return org_user
    
    async def list_all_active(self) -> List[OrgUser]:
        """List all active users in this org"""
        result = await self.db.execute(
            select(OrgUser).where(OrgUser.status == 1)
        )
        return result.scalars().all()
    
    async def update(self, org_user: OrgUser) -> OrgUser:
        """Update org user"""
        merged = await self.db.merge(org_user)
        await self.db.commit()
        await self.db.refresh(merged)
        return merged
    
    async def delete(self, org_user: OrgUser):
        """Remove user from org"""
        await self.db.delete(org_user)
        await self.db.commit()
    
    async def is_user_member(self, user_id: str) -> bool:
        """Check if user is member of this org"""
        result = await self.db.execute(
            select(OrgUser).where(OrgUser.user_id == uuid.UUID(user_id))
        )
        return result.scalar_one_or_none() is not None
    
    async def get_user_count(self) -> int:
        """Get total active user count in this org"""
        result = await self.db.execute(
            select(OrgUser).where(OrgUser.status == 1)
        )
        return len(result.scalars().all())
    
    async def list_all(self) -> List[OrgUser]:
        """List all users in this org"""
        result = await self.db.execute(select(OrgUser))
        return result.scalars().all()
