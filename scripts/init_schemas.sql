-- =====================================================
-- Multi-Tenant System - Database Initialization Script
-- =====================================================
-- This script creates the public schema tables needed for the multi-tenant system
-- Run this BEFORE running Python migrations if not using Alembic

-- =====================================================
-- STEP 1: Create public schema and tables
-- =====================================================

CREATE SCHEMA IF NOT EXISTS public;
SET search_path TO public;

-- Users table (all users globally, no org references)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    status SMALLINT DEFAULT 1 NOT NULL CHECK (status IN (0, 1)),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);
CREATE INDEX IF NOT EXISTS ix_users_email_status ON users(email, status);

-- Organizations table
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    owner_id UUID NOT NULL REFERENCES users(id),
    status SMALLINT DEFAULT 1 NOT NULL CHECK (status IN (0, 1, 2)),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_organizations_slug ON organizations(slug);
CREATE INDEX IF NOT EXISTS ix_organizations_owner_id ON organizations(owner_id);
CREATE INDEX IF NOT EXISTS ix_organizations_slug_status ON organizations(slug, status);

-- =====================================================
-- STEP 2: Create sample tenant schema
-- =====================================================
-- This demonstrates the structure created for EACH organization
-- In production, these schemas are created dynamically via Python

CREATE SCHEMA IF NOT EXISTS tenant_example;
SET search_path TO tenant_example, public;

-- Org users table (tenant-specific membership)
CREATE TABLE IF NOT EXISTS org_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE,  -- FK to public.users (one per user per org)
    email VARCHAR(255) NOT NULL,   -- Denormalized
    first_name VARCHAR(100) NOT NULL,  -- Denormalized
    last_name VARCHAR(100) NOT NULL,   -- Denormalized
    role_type SMALLINT DEFAULT 0 NOT NULL CHECK (role_type IN (0, 1, 2)),
    -- 0 = member, 1 = admin, 2 = owner
    status SMALLINT DEFAULT 1 NOT NULL CHECK (status IN (0, 1, 2)),
    -- 0 = inactive, 1 = active, 2 = pending
    joined_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT uq_org_user_id UNIQUE (user_id)
);

CREATE INDEX IF NOT EXISTS ix_org_users_user_id ON org_users(user_id);
CREATE INDEX IF NOT EXISTS ix_org_users_email ON org_users(email);
CREATE INDEX IF NOT EXISTS ix_org_users_status ON org_users(status);

-- Roles table (tenant-specific)
CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    permissions TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_roles_name ON roles(name);

-- User-Role assignments (tenant-specific)
CREATE TABLE IF NOT EXISTS user_org_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,  -- FK to public.users (NOT org_users.id)
    role_id UUID NOT NULL REFERENCES roles(id),
    assigned_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT uq_user_role UNIQUE (user_id, role_id)
);

CREATE INDEX IF NOT EXISTS ix_user_org_roles_user_id ON user_org_roles(user_id);
CREATE INDEX IF NOT EXISTS ix_user_org_roles_role_id ON user_org_roles(role_id);

-- =====================================================
-- STEP 3: Insert default roles in tenant schema
-- =====================================================

INSERT INTO roles (name, description, permissions) VALUES
    ('Admin', 'Full administrative access', ARRAY['admin', 'manage_users', 'manage_roles', 'view_analytics']),
    ('Manager', 'Team management access', ARRAY['manage_users', 'view_analytics']),
    ('Member', 'Standard user access', ARRAY['view_content', 'create_content'])
ON CONFLICT DO NOTHING;

-- =====================================================
-- STEP 4: Helper Functions
-- =====================================================

-- Function to create tenant schema and tables
CREATE OR REPLACE FUNCTION create_tenant_schema(schema_name TEXT)
RETURNS void AS $$
DECLARE
BEGIN
    EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', schema_name);
    EXECUTE format('SET search_path TO %I, public', schema_name);
    
    -- Create all tenant tables
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.org_users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL UNIQUE,
            email VARCHAR(255) NOT NULL,
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            role_type SMALLINT DEFAULT 0 NOT NULL,
            status SMALLINT DEFAULT 1 NOT NULL,
            joined_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
            CONSTRAINT uq_org_user_id UNIQUE (user_id)
        )
    ', schema_name);
    
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.roles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            description TEXT,
            permissions TEXT[] NOT NULL DEFAULT ''{}'',
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
        )
    ', schema_name);
    
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.user_org_roles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            role_id UUID NOT NULL,
            assigned_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
            CONSTRAINT uq_user_role UNIQUE (user_id, role_id)
        )
    ', schema_name);
    
    -- Create indexes
    EXECUTE format('CREATE INDEX IF NOT EXISTS ix_org_users_user_id ON %I.org_users(user_id)', schema_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS ix_org_users_email ON %I.org_users(email)', schema_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS ix_org_users_status ON %I.org_users(status)', schema_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS ix_roles_name ON %I.roles(name)', schema_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS ix_user_org_roles_user_id ON %I.user_org_roles(user_id)', schema_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS ix_user_org_roles_role_id ON %I.user_org_roles(role_id)', schema_name);
    
END;
$$ LANGUAGE plpgsql;

-- Function to drop tenant schema
CREATE OR REPLACE FUNCTION drop_tenant_schema(schema_name TEXT)
RETURNS void AS $$
BEGIN
    EXECUTE format('DROP SCHEMA IF EXISTS %I CASCADE', schema_name);
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- STEP 5: Sample Data (OPTIONAL - for testing)
-- =====================================================

-- Uncomment to insert test data:
/*
SET search_path TO public;

-- Insert test user
INSERT INTO users (first_name, last_name, email, password_hash, status)
VALUES (
    'John',
    'Doe',
    'john@example.com',
    '$2b$12$KIXxPfxfVMDhyKWLnqF.Uu4.GyECUjKFvj7vgMy8rM9nJzPk3vCFu',  -- bcrypt of 'test123'
    1
) ON CONFLICT DO NOTHING;

-- Insert test organization
INSERT INTO organizations (name, slug, description, owner_id, status)
SELECT 'Test Company', 'test-company', 'A test organization', id, 1
FROM users WHERE email = 'john@example.com'
ON CONFLICT DO NOTHING;
*/

-- =====================================================
-- STEP 6: Verify Tables
-- =====================================================

-- Check public tables
SELECT tablename FROM pg_tables WHERE schemaname = 'public';

-- Check sample tenant schema
SELECT tablename FROM pg_tables WHERE schemaname = 'tenant_example';
