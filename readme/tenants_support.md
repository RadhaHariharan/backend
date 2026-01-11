# Multi-Tenant Organization System - Complete Implementation Guide

## Overview

This implementation provides a flexible multi-tenant architecture where:
- **Users can exist without an organization** (stored in `public` schema)
- **Users can create/join organizations** (tenants)
- **Organization ID (`orgId`) is embedded in JWT tokens**
- **Database schema is determined by `orgId` from token**
- **Schema name = Organization UUID**
- **Some endpoints work with `public` schema only**
- **Some endpoints work with tenant schema only**
- **Some endpoints work with both schemas**

---

## Architecture Flow

```
1. User Registration (No Org)
   ↓
   User created in public.users
   Token: { sub: userId } (no orgId)

2. User Creates/Joins Org
   ↓
   Org created in public.organizations
   Org schema created (schema name = org.id UUID)
   New token: { sub: userId, orgId: orgId }

3. Request with orgId in Token
   ↓
   AuthMiddleware validates token → sets accessTokenData
   ↓
   TenantMiddleware reads orgId from context
   ↓
   If orgId exists → fetch org → set currentOrg context
   ↓
   get_db() → connects to org schema
   get_public_db() → connects to public schema
```

---

## Database Schema Structure

### Public Schema Tables
- `users` - All users (with or without org)
- `organizations` - All organizations/tenants
- Other global tables

### Tenant Schema Tables (per org)
- `roles` - Organization-specific roles
- `user_org_roles` - User role assignments within org
- `projects` - Org-specific data
- Other tenant-specific tables

---

## Step 1: Update User Model (Public Schema)

**File:** `models/user.py`

```python
import uuid
from sqlalchemy import Column, String, SmallInteger, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base
from utils.date_time import utc_now

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "public"}  # Always in public schema

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # Identity
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    # Status: 0 = inactive, 1 = active
    status = Column(SmallInteger, default=1, nullable=False)

    # Audit timestamps
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_users_email_status", "email", "status"),
        {"schema": "public"}
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_active(self) -> bool:
        return self.status == 1
```

---

## Step 2: Create Organization Model (Public Schema)

**File:** `models/organization.py`

```python
import uuid
from sqlalchemy import Column, String, SmallInteger, DateTime, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base
from utils.date_time import utc_now

class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Organization info
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Owner
    owner_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Status: 0 = inactive, 1 = active, 2 = suspended
    status = Column(SmallInteger, default=1, nullable=False)
    
    # Audit
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_organizations_owner_id", "owner_id"),
        Index("ix_organizations_slug_status", "slug", "status"),
        {"schema": "public"}
    )

    def __repr__(self) -> str:
        return f"<Organization id={self.id} name={self.name}>"
    
    @property
    def is_active(self) -> bool:
        return self.status == 1
    
    @property
    def schema_name(self) -> str:
        """Schema name is the organization UUID as string"""
        return str(self.id).replace('-', '_')  # PostgreSQL schema naming
```

---

## Step 3: Create User-Organization Membership Model (Public Schema)

**File:** `models/user_organization.py`

```python
import uuid
from sqlalchemy import Column, SmallInteger, DateTime, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base
from utils.date_time import utc_now

class UserOrganization(Base):
    """Tracks which users belong to which organizations"""
    __tablename__ = "user_organizations"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Role in this org: 0 = member, 1 = admin, 2 = owner
    role_type = Column(SmallInteger, default=0, nullable=False)
    
    # Status: 0 = inactive, 1 = active, 2 = pending
    status = Column(SmallInteger, default=1, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_user_org"),
        Index("ix_user_org_user_id", "user_id"),
        Index("ix_user_org_org_id", "organization_id"),
        {"schema": "public"}
    )

    def __repr__(self) -> str:
        return f"<UserOrganization user={self.user_id} org={self.organization_id}>"
```

---

## Step 4: Create Role Model (Tenant Schema)

**File:** `models/role.py`

```python
import uuid
from sqlalchemy import Column, String, DateTime, Index, Text
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from core.database import Base
from utils.date_time import utc_now

class Role(Base):
    """Organization-specific roles - stored in tenant schema"""
    __tablename__ = "roles"
    # NO __table_args__ with schema - uses tenant schema from search_path

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Permissions as array of strings
    permissions = Column(ARRAY(String), nullable=False, default=list)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_roles_name", "name"),
    )

    def __repr__(self) -> str:
        return f"<Role id={self.id} name={self.name}>"
```

---

## Step 5: Create User-Role Model (Tenant Schema)

**File:** `models/user_org_role.py`

```python
import uuid
from sqlalchemy import Column, DateTime, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base
from utils.date_time import utc_now

class UserOrgRole(Base):
    """User role assignments within an organization - stored in tenant schema"""
    __tablename__ = "user_org_roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    role_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    assigned_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role"),
        Index("ix_user_org_roles_user_id", "user_id"),
        Index("ix_user_org_roles_role_id", "role_id"),
    )

    def __repr__(self) -> str:
        return f"<UserOrgRole user={self.user_id} role={self.role_id}>"
```

---

## Step 6: Update Database Configuration

**File:** `core/database.py`

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from core.config import settings

class Base(DeclarativeBase):
    pass

DATABASE_URL = (
    f"postgresql+asyncpg://"
    f"{settings.DB_USER}:"
    f"{settings.DB_PASSWORD}@"
    f"{settings.DB_HOST}:"
    f"{settings.DB_PORT}/"
    f"{settings.DB_NAME}"
)

engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False
)


async def create_org_schema(org_id: str):
    """
    Create a new PostgreSQL schema for an organization
    Schema name is org UUID with underscores instead of hyphens
    
    Args:
        org_id: Organization UUID string
    """
    schema_name = str(org_id).replace('-', '_')
    
    async with engine.begin() as conn:
        # Create schema
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS \"{schema_name}\""))
        
        # Grant permissions
        await conn.execute(
            text(f"GRANT ALL ON SCHEMA \"{schema_name}\" TO {settings.DB_USER}")
        )
        
        # Set search path and create tables
        await conn.execute(text(f"SET search_path TO \"{schema_name}\", public"))
        
        # Create all tenant-specific tables
        await conn.run_sync(_create_tenant_tables)


def _create_tenant_tables(sync_conn):
    """Create tables in tenant schema (sync function for run_sync)"""
    # Only create tables that don't have schema='public'
    tables_to_create = [
        table for table in Base.metadata.tables.values()
        if not (hasattr(table, 'schema') and table.schema == 'public')
    ]
    
    for table in tables_to_create:
        table.create(sync_conn, checkfirst=True)


async def drop_org_schema(org_id: str):
    """
    Drop an organization's schema (WARNING: Deletes all data!)
    
    Args:
        org_id: Organization UUID string
    """
    schema_name = str(org_id).replace('-', '_')
    async with engine.begin() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS \"{schema_name}\" CASCADE"))
```

---

## Step 7: Update Dependencies

**File:** `api/deps.py`

```python
from typing import AsyncGenerator, Optional
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
        await session.execute(
            text(f"SET search_path TO \"{schema_name}\", public")
        )
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


async def get_dual_db() -> AsyncGenerator[tuple[AsyncSession, Optional[AsyncSession]], None]:
    """
    Get both public and tenant sessions
    Use this when you need to query both schemas
    
    Returns:
        (public_session, tenant_session or None)
    """
    org = currentOrg.get()
    
    async with SessionLocal() as public_session:
        await public_session.execute(text("SET search_path TO public"))
        
        if org:
            async with SessionLocal() as tenant_session:
                schema_name = org.schema_name
                await tenant_session.execute(
                    text(f"SET search_path TO \"{schema_name}\", public")
                )
                try:
                    yield (public_session, tenant_session)
                finally:
                    await tenant_session.close()
        else:
            try:
                yield (public_session, None)
            finally:
                pass
        
        await public_session.close()
```

---

## Step 8: Update Security (Add orgId to Tokens)

**File:** `core/security.py`

```python
import uuid
from jose import jwt
from datetime import timedelta
from typing import Optional
from core.config import settings
from utils.date_time import utc_now
import bcrypt

def create_access_token(data: dict, org_id: Optional[uuid.UUID] = None):
    """
    Create access token with optional orgId
    
    Args:
        data: Token payload (should include 'sub' for user_id)
        org_id: Optional organization UUID to embed in token
    """
    payload = data.copy()
    
    # Convert UUIDs to strings
    for k, v in payload.items():
        if isinstance(v, uuid.UUID):
            payload[k] = str(v)
    
    # Add orgId if provided
    if org_id:
        payload["orgId"] = str(org_id)
    
    payload["exp"] = utc_now() + timedelta(minutes=15)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: uuid.UUID, org_id: Optional[uuid.UUID] = None):
    """
    Create refresh token with optional orgId
    
    Args:
        user_id: User UUID
        org_id: Optional organization UUID
    """
    payload = {
        "sub": str(user_id),
        "exp": utc_now() + timedelta(days=30)
    }
    
    if org_id:
        payload["orgId"] = str(org_id)
    
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashedBytes = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashedBytes.decode('utf-8')


def verify_password(plain, hashed):
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
```

---

## Step 9: Update Tenant Middleware

**File:** `core/middleware/tenant_middleware.py`

```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import contextvars
from typing import List
from sqlalchemy import select, text

from core.database import SessionLocal
from models.organization import Organization
from core.middleware.auth_middleware import accessTokenData

# Context variable to hold current organization
currentOrg: contextvars.ContextVar[Organization] = contextvars.ContextVar("currentOrg", default=None)

class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware to:
    1. Extract orgId from token (set by AuthMiddleware)
    2. Fetch organization from public schema
    3. Set currentOrg context
    
    This runs AFTER AuthMiddleware
    """

    def __init__(self, app, public_routes: List[str] = None):
        super().__init__(app)
        self.public_routes = public_routes or []

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip public routes
        if any(path.startswith(route) for route in self.public_routes):
            return await call_next(request)

        # Get token data from context (set by AuthMiddleware)
        token_data = accessTokenData.get()
        
        # If no orgId in token, continue without setting org context
        # (allows endpoints that don't require org)
        if not token_data or "orgId" not in token_data:
            return await call_next(request)

        org_id = token_data.get("orgId")
        
        # Fetch organization from public schema
        async with SessionLocal() as session:
            await session.execute(text("SET search_path TO public"))
            
            result = await session.execute(
                select(Organization).filter(
                    Organization.id == org_id,
                    Organization.status == 1  # Active only
                )
            )
            org = result.scalar_one_or_none()

        if not org:
            from utils.response import HttpError
            raise HttpError(404, f"Organization not found or inactive", "ORG_NOT_FOUND")

        # Set org in context
        currentOrg.set(org)

        return await call_next(request)
```

---

## Step 10: Create Repositories

### Organization Repository

**File:** `repositories/organization_repo.py`

```python
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from models.organization import Organization
from models.user_organization import UserOrganization

class OrganizationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, org_id: str) -> Optional[Organization]:
        """Get organization by ID"""
        await self.db.execute(text("SET search_path TO public"))
        result = await self.db.execute(
            select(Organization).filter(Organization.id == org_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_slug(self, slug: str) -> Optional[Organization]:
        """Get organization by slug"""
        await self.db.execute(text("SET search_path TO public"))
        result = await self.db.execute(
            select(Organization).filter(Organization.slug == slug)
        )
        return result.scalar_one_or_none()
    
    async def create(self, org: Organization) -> Organization:
        """Create new organization"""
        await self.db.execute(text("SET search_path TO public"))
        self.db.add(org)
        await self.db.commit()
        await self.db.refresh(org)
        return org
    
    async def get_user_organizations(self, user_id: str) -> List[Organization]:
        """Get all organizations a user belongs to"""
        await self.db.execute(text("SET search_path TO public"))
        result = await self.db.execute(
            select(Organization)
            .join(UserOrganization, UserOrganization.organization_id == Organization.id)
            .filter(
                UserOrganization.user_id == user_id,
                UserOrganization.status == 1,
                Organization.status == 1
            )
        )
        return result.scalars().all()
    
    async def add_user_to_org(self, user_id: str, org_id: str, role_type: int = 0) -> UserOrganization:
        """Add user to organization"""
        await self.db.execute(text("SET search_path TO public"))
        user_org = UserOrganization(
            user_id=user_id,
            organization_id=org_id,
            role_type=role_type,
            status=1
        )
        self.db.add(user_org)
        await self.db.commit()
        await self.db.refresh(user_org)
        return user_org
    
    async def is_user_in_org(self, user_id: str, org_id: str) -> bool:
        """Check if user is member of organization"""
        await self.db.execute(text("SET search_path TO public"))
        result = await self.db.execute(
            select(UserOrganization).filter(
                UserOrganization.user_id == user_id,
                UserOrganization.organization_id == org_id,
                UserOrganization.status == 1
            )
        )
        return result.scalar_one_or_none() is not None
```

### Role Repository (Tenant-Scoped)

**File:** `repositories/role_repo.py`

```python
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
            select(Role).filter(Role.id == role_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_name(self, name: str) -> Optional[Role]:
        """Get role by name"""
        result = await self.db.execute(
            select(Role).filter(Role.name == name)
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
            select(Role)
            .join(UserOrgRole, UserOrgRole.role_id == Role.id)
            .filter(UserOrgRole.user_id == user_id)
        )
        return result.scalars().all()
    
    async def assign_role_to_user(self, user_id: str, role_id: str) -> UserOrgRole:
        """Assign role to user"""
        user_role = UserOrgRole(
            user_id=user_id,
            role_id=role_id
        )
        self.db.add(user_role)
        await self.db.commit()
        await self.db.refresh(user_role)
        return user_role
    
    async def remove_role_from_user(self, user_id: str, role_id: str):
        """Remove role from user"""
        result = await self.db.execute(
            select(UserOrgRole).filter(
                UserOrgRole.user_id == user_id,
                UserOrgRole.role_id == role_id
            )
        )
        user_role = result.scalar_one_or_none()
        if user_role:
            await self.db.delete(user_role)
            await self.db.commit()
```

---

## Step 11: Update Permission Service

**File:** `services/permission_service.py`

```python
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from repositories.role_repo import RoleRepository
from utils.response import HttpError


class PermissionService:
    """
    Service to handle permission checking logic
    Works with tenant-scoped roles
    """
    
    def __init__(self, db: AsyncSession, user_id: str):
        """
        Args:
            db: AsyncSession with tenant schema set
            user_id: User ID from token payload
        """
        self.db = db
        self.user_id = user_id
        self.role_repo = RoleRepository(db)
    
    async def check_permissions(
        self, 
        required_permissions: List[str], 
        require_all: bool = False
    ) -> bool:
        """
        Check if user has required permissions in current org
        
        Args:
            required_permissions: List of permission names
            require_all: If True, need ALL. If False, need AT LEAST ONE.
        
        Raises:
            HttpError: If insufficient permissions
        """
        user_permissions = await self._get_user_permissions()
        
        if require_all:
            has_permissions = all(
                permission in user_permissions 
                for permission in required_permissions
            )
            if not has_permissions:
                raise HttpError(
                    status_code=403,
                    message=f"Forbidden: You must have all of these permissions: {', '.join(required_permissions)}",
                    error="INSUFFICIENT_PERMISSIONS"
                )
        else:
            has_permissions = any(
                permission in user_permissions 
                for permission in required_permissions
            )
            if not has_permissions:
                raise HttpError(
                    status_code=403,
                    message=f"Forbidden: You must have at least one of these permissions: {', '.join(required_permissions)}",
                    error="INSUFFICIENT_PERMISSIONS"
                )
        
        return True
    
    async def _get_user_permissions(self) -> List[str]:
        """
        Get list of permissions for user in current org
        Fetches from user's roles in tenant schema
        """
        roles = await self.role_repo.get_user_roles(self.user_id)
        
        permissions = []
        for role in roles:
            if role.permissions:
                permissions.extend(role.permissions)
        
        return list(set(permissions))  # Remove duplicates
```

---

## Step 12: Create Organization Service

**File:** `services/organization_service.py`

```python
import re
from sqlalchemy.ext.asyncio import AsyncSession
from models.organization import Organization
from repositories.organization_repo import OrganizationRepository
from core.database import create_org_schema
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
        text = re.sub(r'[\s_-]+', '-', text)
        text = re.sub(r'^-+|-+$', '', text)
        return text

    async def create_organization(
        self,
        name: str,
        owner_id: str,
        description: str = None,
        slug: str = None
    ) -> Organization:
        """
        Create new organization and add owner as member
        
        Args:
            name: Organization name
            owner_id: User ID who will own this org
            description: Optional description
            slug: Optional slug (auto-generated if not provided)
        """
        # Generate slug
        if not slug:
            slug = self.slugify(name)
        else:
            slug = self.slugify(slug)

        # Check if slug exists
        existing = await self.org_repo.get_by_slug(slug)
        if existing:
            raise HttpError(400, f"Organization with slug '{slug}' already exists", "ORG_SLUG_EXISTS")

        # Create organization
        org = Organization(
            name=name,
            slug=slug,
            description=description,
            owner_id=owner_id,
            status=1
        )

        org = await self.org_repo.create(org)

        # Create schema for organization
        await create_org_schema(str(org.id))

        # Add owner to organization with owner role
        await self.org_repo.add_user_to_org(
            user_id=owner_id,
            org_id=str(org.id),
            role_type=2  # Owner
        )

        return org

    async def get_user_organizations(self, user_id: str):
        """Get all organizations user belongs to"""
        return await self.org_repo.get_user_organizations(user_id)

    async def get_organization(self, org_id: str) -> Organization:
        """Get organization by ID"""
        org = await self.org_repo.get_by_id(org_id)
        if not org:
            raise HttpError(404, "Organization not found", "ORG_NOT_FOUND")
        return org
```

---

## Step 13: Update Auth Service

**File:** `services/auth_service.py`

```python
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from repositories.user_repo import UserRepository
from core.security import verify_password, create_access_token, create_refresh_token, hash_password
from models.user import User

class AuthService:
    def __init__(self, db: AsyncSession):
        self.user_repo = UserRepository(db)

    async def login(self, email: str, password: str, org_id: Optional[str] = None):
        """
        Login user
        
        Args:
            email: User email
            password: User password
            org_id: Optional organization ID to include in token
        """
        user = await self.user_repo.get_by_email(email)

        if not user or not verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials")

        # Create tokens with optional orgId
        return {
            "access_token": create_access_token(
                {"sub": str(user.id), "email": user.email},
                org_id=org_id
            ),
            "refresh_token": create_refresh_token(user.id, org_id=org_id),
            "token_type": "bearer"
        }

    async def register(self, first_name: str, last_name: str, email: str, password: str):
        """Register a new user (NO org required)"""
        # Check if user exists
        existing_user = await self.user_repo.get_by_email(email)
        if existing_user:
            raise ValueError("Email already registered")
        
        # Hash password
        password_hash = hash_password(password)
        
        # Create user
        new_user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password_hash=password_hash,
            status=1
        )
        
        created_user = await self.user_repo.create(new_user)
        
        return {
            "id": str(created_user.id),
            "first_name": created_user.first_name,
            "last_name": created_user.last_name,
            "email": created_user.email
        }
```

---

## Step 14: Create Organization Routes

**File:** `api/v1/routes/organizations.py`

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List

from api.deps import get_public_db
from services.organization_service import OrganizationService
from core.security import create_access_token, create_refresh_token
from utils.response import send_custom_response, HttpError
from utils.token_data import get_current_user_access_token

router = APIRouter(prefix="/organizations", tags=["Organizations"])


class CreateOrgRequest(BaseModel):
    name: str
    description: str = None
    slug: str = None


class OrgResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str = None
    owner_id: str
    status: int
    
    class Config:
        from_attributes = True


class SwitchOrgResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    organization: OrgResponse


@router.post("/", response_model=OrgResponse)
async def create_organization(
    payload: CreateOrgRequest,
    db: AsyncSession = Depends(get_public_db)
):
    """
    Create new organization
    User must be authenticated (has access token)
    """
    token_data = get_current_user_access_token()
    user_id = token_data.get("sub")
    
    org_service = OrganizationService(db)
    
    try:
        org = await org_service.create_organization(
            name=payload.name,
            owner_id=user_id,
            description=payload.description,
            slug=payload.slug
        )
        
        return send_custom_response(
            {
                "id": str(org.id),
                "name": org.name,
                "slug": org.slug,
                "description": org.description,
                "owner_id": str(org.owner_id),
                "status": org.status
            },
            success_message="Organization created successfully",
            status_code=201
        )
    except HttpError:
        raise
    except Exception as e:
        raise HttpError(500, "Failed to create organization", str(e))


@router.get("/my-organizations")
async def get_my_organizations(
    db: AsyncSession = Depends(get_public_db)
):
    """Get all organizations current user belongs to"""
    token_data = get_current_user_access_token()
    user_id = token_data.get("sub")
    
    org_service = OrganizationService(db)
    orgs = await org_service.get_user_organizations(user_id)
    
    return send_custom_response([
        {
            "id": str(org.id),
            "name": org.name,
            "slug": org.slug,
            "description": org.description,
            "owner_id": str(org.owner_id),
            "status": org.status
        }
        for org in orgs
    ])


@router.post("/switch/{org_id}", response_model=SwitchOrgResponse)
async def switch_organization(
    org_id: str,
    db: AsyncSession = Depends(get_public_db)
):
    """
    Switch to a different organization
    Returns new tokens with orgId embedded
    """
    token_data = get_current_user_access_token()
    user_id = token_data.get("sub")
    email = token_data.get("email")
    
    org_service = OrganizationService(db)
    
    # Verify user is member of this org
    from repositories.organization_repo import OrganizationRepository
    org_repo = OrganizationRepository(db)
    
    is_member = await org_repo.is_user_in_org(user_id, org_id)
    if not is_member:
        raise HttpError(403, "You are not a member of this organization", "NOT_ORG_MEMBER")
    
    # Get org details
    org = await org_service.get_organization(org_id)
    
    # Create new tokens with orgId
    new_access_token = create_access_token(
        {"sub": user_id, "email": email},
        org_id=org_id
    )
    new_refresh_token = create_refresh_token(user_id, org_id=org_id)
    
    return send_custom_response({
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "organization": {
            "id": str(org.id),
            "name": org.name,
            "slug": org.slug,
            "description": org.description,
            "owner_id": str(org.owner_id),
            "status": org.status
        }
    }, success_message="Switched organization successfully")


@router.get("/{org_id}")
async def get_organization(
    org_id: str,
    db: AsyncSession = Depends(get_public_db)
):
    """Get organization details"""
    org_service = OrganizationService(db)
    org = await org_service.get_organization(org_id)
    
    return send_custom_response({
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "description": org.description,
        "owner_id": str(org.owner_id),
        "status": org.status
    })
```

---

## Step 15: Create Role Routes (Tenant-Scoped)

**File:** `api/v1/routes/roles.py`

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List

from api.deps import get_db
from repositories.role_repo import RoleRepository
from models.role import Role
from utils.response import send_custom_response, HttpError
from core.decorators import require_permission

router = APIRouter(prefix="/roles", tags=["Roles"])


class CreateRoleRequest(BaseModel):
    name: str
    description: str = None
    permissions: List[str] = []


class RoleResponse(BaseModel):
    id: str
    name: str
    description: str = None
    permissions: List[str]
    
    class Config:
        from_attributes = True


@router.post("/", response_model=RoleResponse)
@require_permission(["manage_roles", "admin"])
async def create_role(
    payload: CreateRoleRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create new role in current organization"""
    role_repo = RoleRepository(db)
    
    # Check if role name exists
    existing = await role_repo.get_by_name(payload.name)
    if existing:
        raise HttpError(400, f"Role '{payload.name}' already exists", "ROLE_EXISTS")
    
    role = Role(
        name=payload.name,
        description=payload.description,
        permissions=payload.permissions
    )
    
    created_role = await role_repo.create(role)
    
    return send_custom_response(
        {
            "id": str(created_role.id),
            "name": created_role.name,
            "description": created_role.description,
            "permissions": created_role.permissions
        },
        success_message="Role created successfully",
        status_code=201
    )


@router.get("/")
async def list_roles(db: AsyncSession = Depends(get_db)):
    """List all roles in current organization"""
    role_repo = RoleRepository(db)
    roles = await role_repo.list_all()
    
    return send_custom_response([
        {
            "id": str(role.id),
            "name": role.name,
            "description": role.description,
            "permissions": role.permissions
        }
        for role in roles
    ])


@router.post("/assign")
@require_permission(["manage_roles", "admin"])
async def assign_role_to_user(
    user_id: str,
    role_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Assign role to user in current organization"""
    role_repo = RoleRepository(db)
    
    user_role = await role_repo.assign_role_to_user(user_id, role_id)
    
    return send_custom_response(
        {
            "user_id": str(user_role.user_id),
            "role_id": str(user_role.role_id),
            "assigned_at": str(user_role.assigned_at)
        },
        success_message="Role assigned successfully"
    )


@router.delete("/unassign")
@require_permission(["manage_roles", "admin"])
async def remove_role_from_user(
    user_id: str,
    role_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Remove role from user in current organization"""
    role_repo = RoleRepository(db)
    
    await role_repo.remove_role_from_user(user_id, role_id)
    
    return send_custom_response(
        None,
        success_message="Role removed successfully"
    )


@router.get("/user/{user_id}")
async def get_user_roles(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all roles assigned to a user in current organization"""
    role_repo = RoleRepository(db)
    roles = await role_repo.get_user_roles(user_id)
    
    return send_custom_response([
        {
            "id": str(role.id),
            "name": role.name,
            "description": role.description,
            "permissions": role.permissions
        }
        for role in roles
    ])
```

---

## Step 16: Update Main Application

**File:** `main.py`

```python
import uvicorn
from fastapi import FastAPI, Request
from api.v1 import router as v1_router
from api.v1.routes.organizations import router as org_router
from api.v1.routes.roles import router as role_router
from core.exception_handlers import setup_exception_handlers, logger
from core.middleware.auth_middleware import AuthMiddleware
from core.middleware.tenant_middleware import TenantMiddleware
from core.config import settings
from utils.response import send_error_response

setup_exception_handlers()
app = FastAPI()

# --- Public routes (no auth required) ---
public_routes = [
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/openapi.json",
    "/docs",
    "/redoc"
]

# Routes that don't require orgId in token
# (user must be authenticated but org is optional)
org_optional_routes = [
    "/api/v1/organizations",
    "/api/v1/auth/refresh"
]

refresh_token_only_routes = []

# --- Middleware (ORDER MATTERS!) ---
# 1. Authentication first (validates token, sets accessTokenData)
app.add_middleware(
    AuthMiddleware,
    public_routes=public_routes,
    refresh_token_only_routes=refresh_token_only_routes
)

# 2. Tenant middleware (reads orgId from token, sets currentOrg)
# Runs after auth so it can access token data
app.add_middleware(
    TenantMiddleware,
    public_routes=public_routes + org_optional_routes
)

# --- Global exception handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(
        f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}"
    )
    return send_error_response(exc)

# --- API Routes ---
app.include_router(org_router, prefix="/api/v1")   # Org management (public schema)
app.include_router(role_router, prefix="/api/v1")  # Roles (tenant schema)
app.include_router(v1_router, prefix="/api/v1")    # Auth routes

if __name__ == "__main__":
    logger.debug("Starting server...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=(settings.ENVIRONMENT == "development")
    )
```

---

## Step 17: Update API Router

**File:** `api/v1/__init__.py`

```python
from fastapi import APIRouter
from api.v1.routes.auth import router as auth_router

router = APIRouter()
router.include_router(auth_router)
```

---

## Usage Flow Examples

### 1. User Registration (No Org)

```bash
# User registers without organization
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com",
    "password": "secure123"
  }'

# Response:
{
  "message": "User registered successfully",
  "statusCode": 200,
  "result": {
    "id": "uuid-here",
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com"
  }
}
```

### 2. User Login (No Org)

```bash
# Login without org
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "secure123"
  }'

# Response - Token has NO orgId:
{
  "access_token": "eyJ...",  # Payload: {sub: userId, email: ...}
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### 3. Create Organization

```bash
# Create org (requires auth token WITHOUT orgId)
curl -X POST http://localhost:8000/api/v1/organizations \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corp",
    "description": "My awesome company"
  }'

# Response:
{
  "message": "Organization created successfully",
  "statusCode": 201,
  "result": {
    "id": "org-uuid-here",
    "name": "Acme Corp",
    "slug": "acme-corp",
    "owner_id": "user-uuid"
  }
}
```

### 4. Switch to Organization

```bash
# Get new tokens with orgId
curl -X POST http://localhost:8000/api/v1/organizations/switch/org-uuid-here \
  -H "Authorization: Bearer eyJ..."

# Response - New tokens WITH orgId:
{
  "message": "Switched organization successfully",
  "result": {
    "access_token": "eyJ...",  # Payload: {sub: userId, orgId: orgId, ...}
    "refresh_token": "eyJ...",
    "token_type": "bearer",
    "organization": {
      "id": "org-uuid",
      "name": "Acme Corp",
      ...
    }
  }
}
```

### 5. Access Tenant-Scoped Endpoints

```bash
# Create role (requires orgId in token)
curl -X POST http://localhost:8000/api/v1/roles \
  -H "Authorization: Bearer eyJ..."  # Token WITH orgId
  -H "Content-Type: application/json" \
  -d '{
    "name": "Admin",
    "permissions": ["manage_users", "manage_roles", "admin"]
  }'

# This works because:
# - AuthMiddleware validates token
# - TenantMiddleware reads orgId from token
# - TenantMiddleware fetches org from public schema
# - get_db() connects to org's schema
# - Role is created in org's schema
```

---

## Key Scenarios Handled

### ✅ Scenario 1: User Without Org
- User registers → stored in `public.users`
- User logs in → token has `{sub: userId}` (NO orgId)
- User can access org management endpoints
- User CANNOT access tenant-scoped endpoints (roles, etc.)

### ✅ Scenario 2: User Creates Org
- User authenticated (token without orgId)
- User creates org → stored in `public.organizations`
- Org schema created (name = org UUID)
- User added to org in `public.user_organizations`
- User switches to org → gets NEW tokens with orgId

### ✅ Scenario 3: User Switches Org
- User has multiple orgs
- User calls `/organizations/switch/{orgId}`
- System verifies user is member
- Returns new tokens with different orgId
- All subsequent requests use new org's schema

### ✅ Scenario 4: Multi-Schema Operations
```python
# Example: Get user from public + user's roles from tenant
from api.deps import get_dual_db

@router.get("/profile-with-roles")
async def get_profile(sessions = Depends(get_dual_db)):
    public_db, tenant_db = sessions
    
    # Query public schema
    user = await UserRepository(public_db).get_by_id(user_id)
    
    # Query tenant schema (if org context exists)
    roles = []
    if tenant_db:
        roles = await RoleRepository(tenant_db).get_user_roles(user_id)
    
    return {
        "user": user,
        "roles": roles
    }
```

---

## Database Migration Script

**File:** `scripts/init_schemas.sql`

```sql
-- =====================================================
-- STEP 1: Create public schema tables
-- =====================================================

CREATE SCHEMA IF NOT EXISTS public;
SET search_path TO public;

-- Users table (all users, with or without org)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    status SMALLINT DEFAULT 1 NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);
CREATE INDEX IF NOT EXISTS ix_users_email_status ON users(email, status);

-- Organizations table
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    owner_id UUID NOT NULL,
    status SMALLINT DEFAULT 1 NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_organizations_slug ON organizations(slug);
CREATE INDEX IF NOT EXISTS ix_organizations_owner_id ON organizations(owner_id);
CREATE INDEX IF NOT EXISTS ix_organizations_slug_status ON organizations(slug, status);

-- User-Organization membership
CREATE TABLE IF NOT EXISTS user_organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    organization_id UUID NOT NULL,
    role_type SMALLINT DEFAULT 0 NOT NULL,  -- 0=member, 1=admin, 2=owner
    status SMALLINT DEFAULT 1 NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    CONSTRAINT uq_user_org UNIQUE (user_id, organization_id)
);

CREATE INDEX IF NOT EXISTS ix_user_org_user_id ON user_organizations(user_id);
CREATE INDEX IF NOT EXISTS ix_user_org_org_id ON user_organizations(organization_id);

-- =====================================================
-- STEP 2: Create first tenant schema (example)
-- =====================================================

-- This shows what gets created for each org
-- Replace 'tenant_example' with actual org UUID

CREATE SCHEMA IF NOT EXISTS tenant_example;
SET search_path TO tenant_example, public;

-- Roles table (tenant-specific)
CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    permissions TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_roles_name ON roles(name);

-- User-Role assignments (tenant-specific)
CREATE TABLE IF NOT EXISTS user_org_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    role_id UUID NOT NULL,
    assigned_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    CONSTRAINT uq_user_role UNIQUE (user_id, role_id)
);

CREATE INDEX IF NOT EXISTS ix_user_org_roles_user_id ON user_org_roles(user_id);
CREATE INDEX IF NOT EXISTS ix_user_org_roles_role_id ON user_org_roles(role_id);

-- =====================================================
-- STEP 3: Insert default roles (per tenant)
-- =====================================================

INSERT INTO roles (name, description, permissions) VALUES
('Admin', 'Full administrative access', ARRAY['admin', 'manage_users', 'manage_roles', 'view_analytics']),
('Manager', 'Team management access', ARRAY['manage_users', 'view_analytics']),
('Member', 'Standard user access', ARRAY['view_content', 'create_content'])
ON CONFLICT DO NOTHING;
```

---

## Testing Guide

### 1. Test User Registration (No Org)
```python
import requests

# Register user
response = requests.post('http://localhost:8000/api/v1/auth/register', json={
    'first_name': 'John',
    'last_name': 'Doe',
    'email': 'john@test.com',
    'password': 'test123'
})
print(response.json())
# Should succeed, user in public.users
```

### 2. Test Org Creation
```python
# Login first
login = requests.post('http://localhost:8000/api/v1/auth/login', json={
    'email': 'john@test.com',
    'password': 'test123'
})
token = login.json()['result']['access_token']

# Create org
org = requests.post(
    'http://localhost:8000/api/v1/organizations',
    headers={'Authorization': f'Bearer {token}'},
    json={'name': 'Test Org'}
)
print(org.json())
# Check database: public.organizations + new schema created
```

### 3. Test Org Switching
```python
org_id = org.json()['result']['id']

# Switch to org
switch = requests.post(
    f'http://localhost:8000/api/v1/organizations/switch/{org_id}',
    headers={'Authorization': f'Bearer {token}'}
)
new_token = switch.json()['result']['access_token']

# Decode token to verify orgId present
import jwt
decoded = jwt.decode(new_token, options={"verify_signature": False})
print(decoded)  # Should have 'orgId' field
```

### 4. Test Tenant-Scoped Operations
```python
# Create role (requires orgId in token)
role = requests.post(
    'http://localhost:8000/api/v1/roles',
    headers={'Authorization': f'Bearer {new_token}'},
    json={
        'name': 'Admin',
        'permissions': ['admin', 'manage_users']
    }
)
print(role.json())
# Check database: role in <org_id> schema, NOT in public
```

---

## Environment Variables

**File:** `.env`

```env
# Environment
ENVIRONMENT=dev

# Database
DB_USER=postgres
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database

# Security
JWT_SECRET_KEY=your-secret-key-here-change-in-production
JWT_ALGORITHM=HS256
```

---

## Summary

### What We Built

1. **Flexible User System**
   - Users can exist without orgs (public schema)
   - Users can create/join multiple orgs
   - Org membership tracked in public.user_organizations

2. **Dynamic Token System**
   - Tokens without orgId for org-less users
   - Tokens with orgId after joining org
   - Org switching updates tokens

3. **Multi-Schema Database**
   - Public schema: users, organizations, memberships
   - Tenant schemas: roles, permissions, org-specific data
   - Schema name = org UUID

4. **Smart Middleware**
   - AuthMiddleware: validates token, sets context
   - TenantMiddleware: reads orgId, fetches org, sets context
   - Dependency system: get_db(), get_public_db(), get_dual_db()

5. **Permission System**
   - Tenant-scoped roles (per org)
   - Permission decorator works with org context
   - Role repository handles tenant schema

### Key Files Created/Modified

- `models/organization.py` - Org model
- `models/user_organization.py` - Membership model
- `models/role.py` - Tenant-scoped roles
- `models/user_org_role.py` - User-role assignments
- `core/middleware/tenant_middleware.py` - Org context
- `core/security.py` - Updated tokens
- `api/deps.py` - Multi-schema sessions
- `repositories/organization_repo.py` - Org queries
- `repositories/role_repo.py` - Tenant-scoped roles
- `services/organization_service.py` - Org operations
- `services/permission_service.py` - Tenant permissions
- `api/v1/routes/organizations.py` - Org endpoints
- `api/v1/routes/roles.py` - Role endpoints
- `main.py` - Updated middleware order

### Next Steps

1. ✅ Run database migrations
2. ✅ Test user registration without org
3. ✅ Test org creation and schema creation
4. ✅ Test org switching and token updates
5. ✅ Test tenant-scoped operations (roles)
6. ✅ Add more tenant-specific models as needed
7. ✅ Implement org invitation system
8. ✅ Add org settings/configuration
9. ✅ Implement billing per org

---

**This implementation gives you complete flexibility: users can work without orgs, create orgs when needed, and seamlessly switch between multiple organizations with proper data isolation.**