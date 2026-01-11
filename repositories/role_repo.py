import uuid
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.role import Role
from models.user_org_role import UserOrgRole


class RoleRepository:
    """
    Role repository - operates on TENANT schema
    Assumes session already has correct search_path set
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, role_id: str) -> Optional[Role]:
        """Get role by ID"""
        result = await self.db.execute(
            select(Role).where(Role.id == uuid.UUID(role_id))
        )
        return result.scalar_one_or_none()
    
    async def get_by_name(self, name: str) -> Optional[Role]:
        """Get role by name"""
        result = await self.db.execute(
            select(Role).where(Role.name == name)
        )
        return result.scalar_one_or_none()
    
    async def create(self, role: Role) -> Role:
        """Create new role"""
        self.db.add(role)
        await self.db.commit()
        await self.db.refresh(role)
        return role
    
    async def list_all(self) -> List[Role]:
        """List all roles in this org"""
        result = await self.db.execute(select(Role))
        return result.scalars().all()
    
    async def get_user_roles(self, user_id: str) -> List[Role]:
        """Get all roles assigned to a user"""
        result = await self.db.execute(
            select(Role).join(
                UserOrgRole,
                Role.id == UserOrgRole.role_id
            ).where(UserOrgRole.user_id == uuid.UUID(user_id))
        )
        return result.scalars().all()
    
    async def assign_role_to_user(self, user_id: str, role_id: str) -> UserOrgRole:
        """Assign role to user"""
        user_role = UserOrgRole(
            user_id=uuid.UUID(user_id),
            role_id=uuid.UUID(role_id)
        )
        self.db.add(user_role)
        await self.db.commit()
        await self.db.refresh(user_role)
        return user_role
    
    async def remove_role_from_user(self, user_id: str, role_id: str):
        """Remove role from user"""
        user_role = await self.db.execute(
            select(UserOrgRole).where(
                (UserOrgRole.user_id == uuid.UUID(user_id)) &
                (UserOrgRole.role_id == uuid.UUID(role_id))
            )
        )
        obj = user_role.scalar_one_or_none()
        if obj:
            await self.db.delete(obj)
            await self.db.commit()
    
    async def update(self, role: Role) -> Role:
        """Update role"""
        merged = await self.db.merge(role)
        await self.db.commit()
        await self.db.refresh(merged)
        return merged
    
    async def delete(self, role: Role):
        """Delete role"""
        await self.db.delete(role)
        await self.db.commit()
