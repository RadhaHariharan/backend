from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from core.config import settings

class Base(DeclarativeBase):
    pass

# Change to async driver
DATABASE_URL = (
    f"postgresql+asyncpg://"  # ← Changed from psycopg2
    f"{settings.DB_USER}:"
    f"{settings.DB_PASSWORD}@"
    f"{settings.DB_HOST}:"
    f"{settings.DB_PORT}/"
    f"{settings.DB_NAME}"
)


# Use async engine
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False
)


# Use async session maker
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
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
        
        # Set search_path to new schema + public
        await conn.execute(text(f'SET search_path TO "{schema_name}", public'))
        
        # Create tables in tenant schema
        await conn.run_sync(_create_tenant_tables)


def _create_tenant_tables(sync_conn):
    """Create tables in tenant schema (sync function for run_sync)"""
    from models.org_user import OrgUser
    from models.role import Role
    from models.user_org_role import UserOrgRole
    
    # Only create tenant-specific tables
    for model in [OrgUser, Role, UserOrgRole]:
        model.metadata.create_all(sync_conn)


async def drop_org_schema(org_id: str):
    """
    Drop an organization's schema (WARNING: Deletes all data!)
    
    Args:
        org_id: Organization UUID string
    """
    schema_name = str(org_id).replace('-', '_')
    async with engine.begin() as conn:
        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))