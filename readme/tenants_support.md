# Multi-Tenant Support Implementation Guide

## Overview
This guide implements multi-tenant architecture using **separate PostgreSQL schemas** per tenant under one database.

**Architecture:**
- One PostgreSQL database
- Each tenant gets its own schema (e.g., `tenant_abc`, `tenant_xyz`)
- Shared `public` schema for tenant metadata
- Dynamic schema switching per request

---

## Step 1: Create Tenant Model (Public Schema)

**File:** `models/tenant.py`

```python
import uuid
from sqlalchemy import Column, String, SmallInteger, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base
from utils.date_time import utc_now

class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = {"schema": "public"}  # Always in public schema

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Tenant identification
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)  # URL-safe identifier
    schema_name = Column(String(63), unique=True, nullable=False)  # PostgreSQL schema name
    
    # Contact info
    email = Column(String(255), nullable=False)
    
    # Status: 0 = inactive, 1 = active, 2 = suspended
    status = Column(SmallInteger, default=1, nullable=False)
    
    # Audit
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_tenants_slug_status", "slug", "status"),
        {"schema": "public"}
    )

    def __repr__(self) -> str:
        return f"<Tenant id={self.id} slug={self.slug} schema={self.schema_name}>"
    
    @property
    def is_active(self) -> bool:
        return self.status == 1
```

---

## Step 2: Update Database Configuration

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


async def get_tenant_session(schema_name: str) -> AsyncSession:
    """
    Get database session with schema set to tenant's schema
    
    Args:
        schema_name: PostgreSQL schema name for the tenant
        
    Returns:
        AsyncSession with search_path set to tenant schema
    """
    async with SessionLocal() as session:
        # Set search_path to tenant schema, then public
        await session.execute(
            text(f"SET search_path TO {schema_name}, public")
        )
        try:
            yield session
        finally:
            await session.close()


async def create_tenant_schema(schema_name: str):
    """
    Create a new PostgreSQL schema for a tenant
    
    Args:
        schema_name: Name of schema to create
    """
    async with engine.begin() as conn:
        # Create schema
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
        
        # Grant permissions (adjust as needed)
        await conn.execute(
            text(f"GRANT ALL ON SCHEMA {schema_name} TO {settings.DB_USER}")
        )


async def drop_tenant_schema(schema_name: str):
    """
    Drop a tenant's schema (WARNING: Deletes all data!)
    
    Args:
        schema_name: Name of schema to drop
    """
    async with engine.begin() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
```

---

## Step 3: Create Tenant Context Middleware

**File:** `core/middleware/tenant_middleware.py`

```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import contextvars
from typing import List
from sqlalchemy import select

from core.database import SessionLocal
from models.tenant import Tenant
from utils.response import HttpError

# Context variable to hold current tenant
currentTenant: contextvars.ContextVar[Tenant] = contextvars.ContextVar("currentTenant", default=None)

class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware to identify tenant from:
    1. X-Tenant-Slug header (recommended)
    2. Subdomain (e.g., acme.yourdomain.com)
    3. Path prefix (e.g., /t/acme/...)
    """

    def __init__(self, app, public_routes: List[str] = None, tenant_header: str = "X-Tenant-Slug"):
        super().__init__(app)
        self.public_routes = public_routes or []
        self.tenant_header = tenant_header

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip public routes
        if any(path.startswith(route) for route in self.public_routes):
            return await call_next(request)

        # --- 1. Try header-based tenant identification ---
        tenant_slug = request.headers.get(self.tenant_header)
        
        # --- 2. Try subdomain-based identification ---
        if not tenant_slug:
            host = request.headers.get("host", "")
            parts = host.split(".")
            if len(parts) > 2:  # e.g., acme.yourdomain.com
                tenant_slug = parts[0]
        
        # --- 3. Try path-based identification ---
        if not tenant_slug and path.startswith("/t/"):
            # e.g., /t/acme/api/v1/users
            path_parts = path.split("/")
            if len(path_parts) > 2:
                tenant_slug = path_parts[2]

        if not tenant_slug:
            raise HttpError(400, "Tenant identifier not found", "TENANT_MISSING")

        # --- Fetch tenant from database ---
        async with SessionLocal() as session:
            result = await session.execute(
                select(Tenant).filter(
                    Tenant.slug == tenant_slug.lower(),
                    Tenant.status == 1  # Active only
                )
            )
            tenant = result.scalar_one_or_none()

        if not tenant:
            raise HttpError(404, f"Tenant '{tenant_slug}' not found or inactive", "TENANT_NOT_FOUND")

        # --- Set tenant in context ---
        currentTenant.set(tenant)

        return await call_next(request)
```

---

## Step 4: Update Dependencies

**File:** `api/deps.py`

```python
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from core.database import SessionLocal
from core.middleware.tenant_middleware import currentTenant
from utils.response import HttpError


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session with tenant schema set
    """
    tenant = currentTenant.get()
    
    if not tenant:
        raise HttpError(500, "Tenant context not set", "TENANT_CONTEXT_MISSING")
    
    async with SessionLocal() as session:
        # Set search_path to tenant's schema
        await session.execute(
            text(f"SET search_path TO {tenant.schema_name}, public")
        )
        try:
            yield session
        finally:
            await session.close()


async def get_public_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session for public schema (tenant management)
    """
    async with SessionLocal() as session:
        await session.execute(text("SET search_path TO public"))
        try:
            yield session
        finally:
            await session.close()
```

---

## Step 5: Update User Model for Multi-Tenant

**File:** `models/user.py`

```python
import uuid
from sqlalchemy import Column, String, SmallInteger, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base
from utils.date_time import utc_now

class User(Base):
    __tablename__ = "users"
    # NO __table_args__ with schema - will use tenant schema from search_path

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    status = Column(SmallInteger, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_users_email_status", "email", "status"),
    )
```

---

## Step 6: Create Tenant Management Service

**File:** `services/tenant_service.py`

```python
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.tenant import Tenant
from core.database import create_tenant_schema, Base, engine
from utils.response import HttpError


class TenantService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def slugify(text: str) -> str:
        """Convert text to URL-safe slug"""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s_-]+', '-', text)
        text = re.sub(r'^-+|-+$', '', text)
        return text

    async def create_tenant(
        self, 
        name: str, 
        email: str, 
        slug: str = None
    ) -> Tenant:
        """
        Create a new tenant with dedicated schema
        
        Args:
            name: Tenant display name
            email: Tenant contact email
            slug: URL-safe identifier (auto-generated if not provided)
        """
        # Generate slug if not provided
        if not slug:
            slug = self.slugify(name)
        else:
            slug = self.slugify(slug)

        # Check if slug already exists
        result = await self.db.execute(
            select(Tenant).filter(Tenant.slug == slug)
        )
        if result.scalar_one_or_none():
            raise HttpError(400, f"Tenant with slug '{slug}' already exists", "TENANT_EXISTS")

        # Generate schema name (prefix with tenant_ for clarity)
        schema_name = f"tenant_{slug}"

        # Create tenant record
        tenant = Tenant(
            name=name,
            slug=slug,
            email=email,
            schema_name=schema_name,
            status=1
        )

        self.db.add(tenant)
        await self.db.commit()
        await self.db.refresh(tenant)

        # Create PostgreSQL schema
        await create_tenant_schema(schema_name)

        # Create tables in tenant schema
        await self._initialize_tenant_schema(schema_name)

        return tenant

    async def _initialize_tenant_schema(self, schema_name: str):
        """
        Create all tables in the tenant's schema
        """
        async with engine.begin() as conn:
            # Set search_path to tenant schema
            await conn.execute(
                text(f"SET search_path TO {schema_name}, public")
            )
            
            # Create all tables defined in Base metadata
            # Exclude tables that are explicitly in 'public' schema
            await conn.run_sync(
                lambda sync_conn: Base.metadata.create_all(
                    sync_conn,
                    tables=[
                        table for table in Base.metadata.tables.values()
                        if table.schema != 'public'
                    ]
                )
            )

    async def get_tenant_by_slug(self, slug: str) -> Tenant:
        """Get tenant by slug"""
        result = await self.db.execute(
            select(Tenant).filter(Tenant.slug == slug)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HttpError(404, f"Tenant '{slug}' not found", "TENANT_NOT_FOUND")
        return tenant

    async def list_tenants(self):
        """List all tenants"""
        result = await self.db.execute(select(Tenant))
        return result.scalars().all()

    async def update_tenant_status(self, tenant_id: str, status: int):
        """Update tenant status (0=inactive, 1=active, 2=suspended)"""
        result = await self.db.execute(
            select(Tenant).filter(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HttpError(404, "Tenant not found", "TENANT_NOT_FOUND")
        
        tenant.status = status
        await self.db.commit()
        return tenant
```

---

## Step 7: Create Tenant Management Routes

**File:** `api/v1/routes/tenants.py`

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr

from api.deps import get_public_db
from services.tenant_service import TenantService
from utils.response import send_custom_response, HttpError

router = APIRouter(prefix="/tenants", tags=["Tenants"])


class CreateTenantRequest(BaseModel):
    name: str
    email: EmailStr
    slug: str = None


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    schema_name: str
    email: str
    status: int
    
    class Config:
        from_attributes = True


@router.post("/", response_model=TenantResponse)
async def create_tenant(
    payload: CreateTenantRequest,
    db: AsyncSession = Depends(get_public_db)
):
    """
    Create a new tenant with dedicated schema
    
    NOTE: Uses public schema database session
    """
    tenant_service = TenantService(db)
    
    try:
        tenant = await tenant_service.create_tenant(
            name=payload.name,
            email=payload.email,
            slug=payload.slug
        )
        
        return send_custom_response(
            {
                "id": str(tenant.id),
                "name": tenant.name,
                "slug": tenant.slug,
                "schema_name": tenant.schema_name,
                "email": tenant.email,
                "status": tenant.status
            },
            success_message="Tenant created successfully",
            status_code=201
        )
    except HttpError:
        raise
    except Exception as e:
        raise HttpError(500, "Failed to create tenant", str(e))


@router.get("/")
async def list_tenants(db: AsyncSession = Depends(get_public_db)):
    """List all tenants"""
    tenant_service = TenantService(db)
    tenants = await tenant_service.list_tenants()
    
    return send_custom_response([
        {
            "id": str(t.id),
            "name": t.name,
            "slug": t.slug,
            "schema_name": t.schema_name,
            "status": t.status
        }
        for t in tenants
    ])


@router.get("/{slug}")
async def get_tenant(
    slug: str,
    db: AsyncSession = Depends(get_public_db)
):
    """Get tenant by slug"""
    tenant_service = TenantService(db)
    tenant = await tenant_service.get_tenant_by_slug(slug)
    
    return send_custom_response({
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "schema_name": tenant.schema_name,
        "email": tenant.email,
        "status": tenant.status
    })
```

---

## Step 8: Update Main Application

**File:** `main.py`

```python
import uvicorn
from fastapi import FastAPI, Request
from api.v1 import router as v1_router
from api.v1.routes.tenants import router as tenant_router
from core.exception_handlers import setup_exception_handlers, logger
from core.middleware.auth_middleware import AuthMiddleware
from core.middleware.tenant_middleware import TenantMiddleware
from core.config import settings
from utils.response import send_error_response

setup_exception_handlers()
app = FastAPI()

# --- Public routes (no auth, no tenant) ---
public_routes = [
    "/api/v1/tenants",  # Tenant management
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/openapi.json",
    "/docs",
    "/redoc"
]

refresh_token_only_routes = []

# --- Middleware (ORDER MATTERS!) ---
# 1. Tenant identification (before auth)
app.add_middleware(
    TenantMiddleware,
    public_routes=public_routes,
    tenant_header="X-Tenant-Slug"
)

# 2. Authentication (after tenant)
app.add_middleware(
    AuthMiddleware,
    public_routes=public_routes,
    refresh_token_only_routes=refresh_token_only_routes
)

# --- Global exception handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(
        f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}"
    )
    return send_error_response(exc)

# --- API Routes ---
app.include_router(tenant_router, prefix="/api/v1")  # Tenant management
app.include_router(v1_router, prefix="/api/v1")      # Tenant-scoped routes

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

## Step 9: Update API V1 Router

**File:** `api/v1/__init__.py`

```python
from fastapi import APIRouter
from api.v1.routes.auth import router as auth_router

router = APIRouter()
router.include_router(auth_router)
```

---

## Step 10: Add Tenant Context Helper

**File:** `utils/tenant.py`

```python
from core.middleware.tenant_middleware import currentTenant
from models.tenant import Tenant
from utils.response import HttpError


def get_current_tenant() -> Tenant:
    """
    Get current tenant from context
    
    Returns:
        Tenant: Current tenant object
        
    Raises:
        HttpError: If tenant not found in context
    """
    tenant = currentTenant.get()
    if not tenant:
        raise HttpError(500, "Tenant context not set", "TENANT_CONTEXT_MISSING")
    return tenant


def get_tenant_id() -> str:
    """Get current tenant ID"""
    return str(get_current_tenant().id)


def get_tenant_slug() -> str:
    """Get current tenant slug"""
    return get_current_tenant().slug


def get_tenant_schema() -> str:
    """Get current tenant schema name"""
    return get_current_tenant().schema_name
```

---

## Usage Examples

### 1. Create a Tenant

```bash
curl -X POST http://localhost:8000/api/v1/tenants \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corporation",
    "email": "admin@acme.com",
    "slug": "acme"
  }'
```

### 2. Access Tenant-Scoped Endpoints

```bash
# Using header
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "X-Tenant-Slug: acme" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@acme.com",
    "password": "secure123"
  }'

# Using subdomain (if DNS configured)
curl -X POST http://acme.yourdomain.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '...'
```

### 3. In Your Route Handlers

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from api.deps import get_db
from utils.tenant import get_current_tenant

router = APIRouter()

@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    tenant = get_current_tenant()
    # All queries automatically use tenant's schema
    # Users will only see data from their tenant
    return {"tenant": tenant.name, "message": "Welcome!"}
```

---

## Database Migration

### Initial Setup

```sql
-- 1. Create public schema tables (tenants)
CREATE SCHEMA IF NOT EXISTS public;

-- 2. Create tenants table in public schema
-- (Use Alembic or run manually)

-- 3. Create first tenant
INSERT INTO public.tenants (id, name, slug, schema_name, email, status)
VALUES (
    gen_random_uuid(),
    'Default Tenant',
    'default',
    'tenant_default',
    'admin@default.com',
    1
);

-- 4. Create schema and tables for first tenant
CREATE SCHEMA tenant_default;
SET search_path TO tenant_default, public;
-- Run your table creation scripts
```

---

## Key Benefits

✅ **Data Isolation**: Each tenant's data in separate schema  
✅ **Performance**: Better than row-level isolation  
✅ **Scalability**: Easy to move schemas to different databases later  
✅ **Security**: PostgreSQL schema-level permissions  
✅ **Migrations**: Can version schemas independently  
✅ **Debugging**: Easy to inspect tenant-specific data  

---

## Next Steps

1. ✅ Create `tenants` table in `public` schema
2. ✅ Test tenant creation endpoint
3. ✅ Test tenant-scoped auth endpoints
4. ✅ Add Alembic migrations for schema management
5. ✅ Implement tenant-aware permission system
6. ✅ Add tenant metrics/monitoring