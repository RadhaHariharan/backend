import re
import uuid
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from models.families import Family
from models.org_user import OrgUser
from repositories.organization_repo import OrganizationRepository
from repositories.org_user_repo import OrgUserRepository
from repositories.user_repo import UserRepository
from core.database import create_org_schema, SessionLocal
from utils.response import HttpError


class OrganizationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.org_repo = OrganizationRepository(db)

    @staticmethod
    def slugify(text: str) -> str:
        """Convert text to URL-safe slug"""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text.strip('-')

    async def create_organization(
        self,
        name: str,
        owner_id: str,
        description: str = None,
        slug: str = None
    ) -> Family:
        """
        Create a new organization
        
        Steps:
        1. Create organization in public schema
        2. Create org-specific schema
        3. Add owner to org_users in new schema
        
        Args:
            name: Organization name
            owner_id: UUID of user creating the org
            description: Optional description
            slug: Optional custom slug (auto-generated if not provided)
            
        Returns:
            Organization object
        """
        # Generate slug if not provided
        if not slug:
            slug = self.slugify(name)
        
        # Check if slug already exists
        existing = await self.org_repo.get_by_slug(slug)
        if existing:
            raise HttpError(400, f"Slug '{slug}' already exists", "SLUG_EXISTS")
        
        # Get owner user details
        user_repo = UserRepository(self.db)
        owner = await user_repo.get_by_id(owner_id)
        if not owner:
            raise HttpError(400, "Owner user not found", "USER_NOT_FOUND")
        
        # Create organization in public schema
        org = Family(
            name=name,
            slug=slug,
            description=description,
            owner_id=uuid.UUID(owner_id),
            status=1
        )
        org = await self.org_repo.create(org)
        
        # Create org schema
        try:
            await create_org_schema(str(org.id))
        except Exception as e:
            # Rollback org creation if schema creation fails
            await self.org_repo.delete(org)
            raise HttpError(500, "Failed to create organization schema", str(e))
        
        # Add owner to org_users in the new schema
        try:
            async with SessionLocal() as tenant_session:
                # Set search_path to org schema
                await tenant_session.execute(
                    text(f'SET search_path TO "{org.schema_name}", public')
                )
                
                # Create org user for owner
                org_user = OrgUser(
                    user_id=uuid.UUID(owner_id),
                    email=owner.email,
                    first_name=owner.first_name,
                    last_name=owner.last_name,
                    role_type=2,  # owner
                    status=1
                )
                
                org_user_repo = OrgUserRepository(tenant_session)
                await org_user_repo.create(org_user)
        except Exception as e:
            raise HttpError(500, "Failed to add owner to organization", str(e))
        
        return org

    async def get_organization(self, org_id: str) -> Family:
        """Get organization by ID"""
        org = await self.org_repo.get_by_id(org_id)
        if not org:
            raise HttpError(404, "Organization not found", "ORG_NOT_FOUND")
        return org

    async def get_user_organizations(self, user_id: str) -> List[Dict]:
        """
        Get all organizations a user belongs to
        
        Note: This requires querying each org schema's org_users table
        For now, we'll get orgs owned by user
        """
        orgs = await self.org_repo.list_by_owner(user_id)
        
        result = []
        for org in orgs:
            result.append({
                "id": str(org.id),
                "name": org.name,
                "slug": org.slug,
                "description": org.description,
                "owner_id": str(org.owner_id),
                "status": org.status,
                "created_at": org.created_at,
            })
        
        return result

    async def is_user_in_org(self, user_id: str, org_id: str) -> bool:
        """Check if user is member of organization"""
        try:
            org = await self.get_organization(org_id)
            
            # Query org's schema
            async with SessionLocal() as tenant_session:
                await tenant_session.execute(
                    text(f'SET search_path TO "{org.schema_name}", public')
                )
                
                org_user_repo = OrgUserRepository(tenant_session)
                return await org_user_repo.is_user_member(user_id)
        except Exception:
            return False

    async def add_user_to_org(
        self,
        user_id: str,
        org_id: str,
        role_type: int = 0
    ) -> OrgUser:
        """
        Add user to organization
        
        Args:
            user_id: User UUID
            org_id: Organization UUID
            role_type: 0=member, 1=admin, 2=owner
            
        Returns:
            OrgUser object
        """
        org = await self.get_organization(org_id)
        
        # Get user details from public schema
        user_repo = UserRepository(self.db)
        user = await user_repo.get_by_id(user_id)
        if not user:
            raise HttpError(400, "User not found", "USER_NOT_FOUND")
        
        # Add to org schema
        async with SessionLocal() as tenant_session:
            await tenant_session.execute(
                text(f'SET search_path TO "{org.schema_name}", public')
            )
            
            org_user = OrgUser(
                user_id=uuid.UUID(user_id),
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                role_type=role_type,
                status=1
            )
            
            org_user_repo = OrgUserRepository(tenant_session)
            return await org_user_repo.create(org_user)
