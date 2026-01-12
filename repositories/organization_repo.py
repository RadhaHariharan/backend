import uuid
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from models.families import Family


class OrganizationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, org_id: str) -> Optional[Family]:
        """Get organization by ID"""
        result = await self.db.execute(
            select(Family).where(Family.id == uuid.UUID(org_id))
        )
        return result.scalar_one_or_none()
    
    async def get_by_slug(self, slug: str) -> Optional[Family]:
        """Get organization by slug"""
        result = await self.db.execute(
            select(Family).where(Family.slug == slug)
        )
        return result.scalar_one_or_none()
    
    async def create(self, org: Family) -> Family:
        """Create new organization"""
        self.db.add(org)
        await self.db.commit()
        await self.db.refresh(org)
        return org
    
    async def list_all_active(self) -> List[Family]:
        """List all active organizations"""
        result = await self.db.execute(
            select(Family).where(Family.status == 1)
        )
        return result.scalars().all()
    
    async def list_by_owner(self, owner_id: str) -> List[Family]:
        """List all organizations owned by a user"""
        result = await self.db.execute(
            select(Family).where(Family.owner_id == uuid.UUID(owner_id))
        )
        return result.scalars().all()
    
    async def update(self, org: Family) -> Family:
        """Update organization"""
        await self.db.merge(org)
        await self.db.commit()
        return org
    
    async def delete(self, org: Family):
        """Delete organization"""
        await self.db.delete(org)
        await self.db.commit()
