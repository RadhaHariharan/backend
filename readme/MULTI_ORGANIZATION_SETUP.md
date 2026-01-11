# Multi-Organization Setup - In Depth Guide

This document provides a comprehensive explanation of how the multi-tenant organization system works, from database architecture to user workflows.

## Table of Contents
1. [Core Concepts](#core-concepts)
2. [Database Architecture](#database-architecture)
3. [Schema Management](#schema-management)
4. [User & Organization Workflow](#user--organization-workflow)
5. [Token System](#token-system)
6. [Data Flow Examples](#data-flow-examples)
7. [Key Implementation Details](#key-implementation-details)

---

## Core Concepts

### What is Multi-Tenancy?

Multi-tenancy is an architecture where a single application instance serves multiple customers (organizations) with complete data isolation. Each organization has:

- **Own PostgreSQL Schema** - Separate namespace for all org-specific tables
- **Isolated Data** - Complete physical separation via PostgreSQL's search_path
- **Independent Roles** - Organization-specific access controls
- **Shared Infrastructure** - Single FastAPI server, single database server

### Why This Approach?

| Aspect | Benefit |
|--------|---------|
| **Data Isolation** | Each org's data is completely separate at the database level |
| **Scalability** | Schemas can be distributed across databases if needed |
| **Security** | No accidental data leakage between orgs |
| **Performance** | Indexes per schema improve query performance |
| **Flexibility** | Easy to add new orgs without code deployment |

---

## Database Architecture

### Global Public Schema

The `public` schema contains **global** data that all organizations share:

```
┌─────────────────────────────────────┐
│         PUBLIC SCHEMA               │
├─────────────────────────────────────┤
│ users                               │
│  ├── id (UUID)                      │
│  ├── first_name                     │
│  ├── last_name                      │
│  ├── email (unique)                 │
│  ├── password_hash                  │
│  ├── status (active/inactive)       │
│  ├── created_at                     │
│  └── updated_at                     │
│                                     │
│ organizations                       │
│  ├── id (UUID)                      │
│  ├── name                           │
│  ├── slug (unique)                  │
│  ├── description                    │
│  ├── owner_id (FK → users.id)       │
│  ├── status                         │
│  ├── created_at                     │
│  └── updated_at                     │
└─────────────────────────────────────┘
```

**Key Points:**
- Users are stored globally once in `public.users`
- One user can be part of multiple organizations
- Organizations track their owner via `owner_id`
- Both tables have indexes on frequently-searched columns (email, slug)

### Tenant-Specific Schemas

For each organization, a **separate schema** is created:

```
Example: Organization with UUID "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
Schema Name: a1b2c3d4_e5f6_7890_abcd_ef1234567890

┌──────────────────────────────────────────┐
│  TENANT SCHEMA (org-specific)            │
├──────────────────────────────────────────┤
│ org_users                                │
│  ├── id (UUID)                           │
│  ├── user_id (FK → public.users.id)      │
│  ├── email (denormalized)                │
│  ├── first_name (denormalized)           │
│  ├── last_name (denormalized)            │
│  ├── role_type (0=member, 1=admin, 2=owner)│
│  ├── status                              │
│  ├── joined_at                           │
│  └── updated_at                          │
│  └── UNIQUE(user_id)                     │
│                                          │
│ roles                                    │
│  ├── id (UUID)                           │
│  ├── name                                │
│  ├── description                         │
│  ├── permissions (PostgreSQL array)      │
│  ├── created_at                          │
│  └── updated_at                          │
│                                          │
│ user_org_roles                           │
│  ├── id (UUID)                           │
│  ├── user_id (FK)                        │
│  ├── role_id (FK → roles.id)             │
│  ├── assigned_at                         │
│  └── UNIQUE(user_id, role_id)            │
└──────────────────────────────────────────┘
```

**Denormalization in org_users:**
- `email`, `first_name`, `last_name` are **copied** from `public.users`
- Avoids cross-schema JOINs (performance optimization)
- Updated when user syncs or org is accessed
- Enables faster queries within the tenant schema

---

## Schema Management

### Schema Naming Convention

Organization UUIDs are converted to PostgreSQL-safe schema names:

```python
# Example conversion
UUID: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
      └─ Replace hyphens with underscores
Schema: "a1b2c3d4_e5f6_7890_abcd_ef1234567890"
```

**Why?** PostgreSQL schema names allow hyphens in quoted names, but unquoted names don't. This approach keeps queries simple.

### Schema Creation Flow

When a user creates an organization:

```
1. User calls: POST /api/v1/organizations
   ├── Request: { name, slug, description? }
   └── Auth: Must be logged in (any user can create orgs)

2. OrganizationService.create_organization()
   ├── Step 1: Validate slug uniqueness in public.organizations
   ├── Step 2: Create row in public.organizations
   │           └── Set owner_id to current user
   ├── Step 3: Call create_org_schema(org_uuid)
   │           └── CREATE SCHEMA IF NOT EXISTS schema_name
   ├── Step 4: Call _create_tenant_tables()
   │           └── Create org_users, roles, user_org_roles tables
   ├── Step 5: Add current user to org as owner
   │           ├── Insert into org_users (with role_type=2)
   │           └── Create default "Owner" role with admin permissions
   └── Step 6: Return organization details

3. Database State After:
   ├── public.organizations: 1 row (new org)
   ├── public.users: unchanged
   └── New schema created with empty org_users/roles/user_org_roles
```

### Schema Deletion Flow

When an organization is deleted:

```
1. User calls: DELETE /api/v1/organizations/{org_id}
   └── Auth: Must be organization owner

2. Database Operations:
   ├── Check user is owner of org
   ├── Drop schema with: DROP SCHEMA schema_name CASCADE
   │  └── All tables, indexes, and functions in schema are deleted
   └── Delete from public.organizations

3. Result: Complete org data is purged
```

---

## User & Organization Workflow

### User Registration (No Organization)

```
1. User calls: POST /api/v1/auth/register
   └── Request: { first_name, last_name, email, password }

2. AuthService.register()
   ├── Validate email not already in public.users
   ├── Hash password with bcrypt
   ├── Insert into public.users
   └── Return user details (without password)

3. User Token (No Organization):
   {
     "sub": "user-uuid",
     "email": "user@example.com",
     "exp": 1234567890
   }
   └── NO orgId field yet
```

**State:** User exists globally but isn't part of any organization.

### Creating First Organization

```
1. User calls: POST /api/v1/organizations
   └── Authorized with token (no orgId)

2. System creates:
   ├── Row in public.organizations
   ├── New PostgreSQL schema
   ├── Three empty tables in schema
   ├── Adds user to org as owner (role_type=2)
   └── Creates default "Owner" role

3. Result:
   - User is now part of 1 organization
   - User can switch to it to get org-scoped token
```

### Switching to Organization

```
1. User calls: POST /api/v1/organizations/switch/{org_id}
   └── Authorized with token (may or may not have orgId)

2. System checks:
   ├── User is member of this org
   │  (verified by querying org_users table in org's schema)
   └── Get user's role info from that org

3. New Token (WITH Organization):
   {
     "sub": "user-uuid",
     "email": "user@example.com",
     "orgId": "org-uuid",  ← NEW
     "exp": 1234567890
   }

4. Result:
   - Token now includes orgId
   - All subsequent requests use org's schema
   - User can access org-specific roles and data
```

### Accessing Organization Data

```
Request Flow with Org Token:

GET /api/v1/roles
Headers: Authorization: Bearer <token_with_orgId>

1. AuthMiddleware
   └── Validates token, extracts orgId

2. TenantMiddleware
   ├── Extracts orgId from token
   ├── Fetches organization from public.organizations
   ├── Sets context variable: currentOrg = {id, schema_name, ...}
   └── Sets database search_path to target schema

3. Route Handler (GET /api/v1/roles)
   └── Injects session via get_db()
      ├── Session has search_path = "org_schema, public"
      └── Queries execute in org's schema by default

4. Database Query:
   SELECT * FROM roles
   └── Executes as: SELECT * FROM org_schema.roles
      (because search_path directs it there)

5. Response:
   {
     "result": [
       { id, name, description, permissions },
       ...
     ]
   }
```

---

## Token System

### Token Structure

The JWT token is a JSON Web Token containing:

```json
{
  "sub": "user-uuid",           // Subject (user ID)
  "email": "user@example.com",  // User email
  "orgId": "org-uuid",          // OPTIONAL: included only if switched to org
  "exp": 1234567890             // Expiration timestamp
}
```

### Token Lifecycle

```
1. Initial Login → Token WITHOUT orgId
   └── Use for: user profile, org management, switching orgs

2. Switch to Org → Token WITH orgId
   └── Use for: role management, org-specific operations

3. Token Expiration → Request new token
   └── Via refresh token endpoint

4. Switch to Different Org → Get NEW token WITH different orgId
   └── All subsequent requests use new org's schema
```

### Multiple Tokens in Use

A user might have multiple valid tokens:

```
User "alice@example.com"
├── Token 1 (no orgId): for org management
├── Token 2 (orgId=org-1): for accessing Acme Corp
└── Token 3 (orgId=org-2): for accessing TechCorp

Each token independently identifies which org to use
```

---

## Data Flow Examples

### Example 1: User Creates Organization and Adds Member

```
Scenario: Alice creates "Acme Corp" and invites Bob

Step 1: Alice creates organization
  POST /api/v1/organizations
  Body: { name: "Acme Corp", slug: "acme-corp" }
  
  Database Changes:
  ├── public.organizations: INSERT (owner_id=alice_uuid)
  └── CREATE SCHEMA acme_corp_uuid

Step 2: Alice switches to the organization
  POST /api/v1/organizations/switch/acme_corp_uuid
  
  Response: { access_token: <with orgId>, refresh_token, organization }
  
  Token now contains orgId=acme_corp_uuid

Step 3: Alice invites Bob to organization
  POST /api/v1/roles/assign (or custom invite endpoint)
  Body: { user_id: bob_uuid }
  
  Database Changes:
  ├── In acme_corp schema:
  │  ├── org_users: INSERT (user_id=bob_uuid, email=bob@..., role_type=0)
  │  └── user_org_roles: INSERT (user_id=bob_uuid, role_id=...)

Step 4: Bob accepts and switches to organization
  POST /api/v1/organizations/switch/acme_corp_uuid
  
  Authentication:
  ├── Verify bob is in acme_corp_uuid (check org_users table)
  ├── Fetch bob's roles from user_org_roles
  └── Generate token with orgId=acme_corp_uuid

Step 5: Bob can now access org data
  GET /api/v1/roles
  
  Database Query:
  ├── search_path = "acme_corp_uuid, public"
  ├── Query acme_corp_uuid.roles
  └── Return Bob's org's roles only
```

### Example 2: Role-Based Access Control

```
Scenario: Alice (admin) creates role, assigns to Bob

Step 1: Alice (in acme_corp org) creates role
  POST /api/v1/roles
  Body: {
    name: "Manager",
    permissions: ["manage_users", "view_reports"]
  }
  
  Database:
  ├── In acme_corp schema:
  │  └── roles: INSERT (id=..., name="Manager", permissions=[...])

Step 2: Alice assigns role to Bob
  POST /api/v1/roles/assign
  Body: { user_id: bob_uuid, role_id: manager_role_uuid }
  
  Database:
  ├── In acme_corp schema:
  │  └── user_org_roles: INSERT (user_id=bob_uuid, role_id=manager_role_uuid)

Step 3: Bob switches to acme_corp and makes request
  GET /api/v1/protected-endpoint
  
  Middleware checks:
  ├── Verify token valid
  ├── Extract orgId and currentOrg
  ├── Fetch Bob's roles from org's user_org_roles table
  ├── Check if "manage_users" is in any of Bob's roles' permissions
  └── Allow/deny based on permission check

Step 4: Result
  ├── If authorized: 200 OK with data
  └── If not authorized: 403 Forbidden
```

### Example 3: Cross-Organization Isolation

```
Scenario: Ensuring Alice (Acme Corp) can't see TechCorp's data

Alice's Access (in Acme Corp):
├── Token orgId: acme_corp_uuid
├── search_path: "acme_corp_uuid, public"
└── Query SELECT * FROM roles
    └── Executes: SELECT * FROM acme_corp_uuid.roles
       └── Only sees Acme Corp's roles

Bob's Access (in TechCorp):
├── Token orgId: techcorp_uuid
├── search_path: "techcorp_uuid, public"
└── Query SELECT * FROM roles
    └── Executes: SELECT * FROM techcorp_uuid.roles
       └── Only sees TechCorp's roles

Guarantee: Even if Alice tries to query,
she gets permission denied at application level
(current token doesn't match requested org)
```

---

## Key Implementation Details

### 1. Database Connection & Search Path

```python
# In core/database.py
def get_db(org_id: UUID):
    """
    Returns a session with search_path set to organization's schema
    """
    session = SessionLocal()
    org = get_organization(org_id)  # Fetch from public schema
    schema_name = org.schema_name   # Convert UUID to schema name
    
    # Set search path: "org_schema, public"
    # This makes queries hit org_schema first, then fall back to public
    session.execute(f"SET search_path TO '{schema_name}', 'public'")
    
    return session
```

**Why search_path?**
- Without it: queries would default to public schema
- With it: queries automatically use org's schema unless explicitly qualified
- Prevents accidental cross-org data access

### 2. Token Validation with OrgId

```python
# In core/security.py
def create_access_token(data: dict, org_id: Optional[UUID] = None):
    to_encode = data.copy()
    
    if org_id:
        to_encode["orgId"] = str(org_id)  # Add orgId if provided
    
    # Encode and sign with JWT_SECRET_KEY
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm="HS256")
```

**Impact:**
- Tokens without orgId: can only access public schema endpoints
- Tokens with orgId: automatically scoped to that org

### 3. Middleware Chain for Multi-Tenant Requests

```python
# In main.py
app.add_middleware(TenantMiddleware)
app.add_middleware(AuthMiddleware)

# Request flow (bottom to top):
# 1. Request arrives
# 2. AuthMiddleware: validates JWT, extracts token data
# 3. TenantMiddleware: uses orgId from token, sets up schema context
# 4. Route handler: receives pre-configured session

# This ensures EVERY request to protected routes automatically
# gets the correct schema context
```

### 4. Lazy User Sync

When a user is added to an organization, their data is denormalized:

```python
# In org_users table: copies from public.users
{
  user_id: "uuid-1",
  email: "alice@example.com",      # Copied from public.users
  first_name: "Alice",              # Copied from public.users
  last_name: "Smith",               # Copied from public.users
  role_type: 2,
  joined_at: "2026-01-11"
}
```

**Benefit:** No cross-schema JOINs needed for org user queries

---

## Security Guarantees

### Data Isolation Guarantees

1. **Physical Schema Separation**
   - Each org's data in separate PostgreSQL schema
   - Database permissions can enforce isolation

2. **Application-Level Checks**
   - Every request validated by AuthMiddleware
   - OrgId from token matched against request scope
   - Invalid org access returns 403 Forbidden

3. **No SQL Injection Risks**
   - Search path set programmatically (never user input)
   - All queries use parameterized statements
   - Schema names pre-validated before use

### Permission Model

```
User → Role → Permissions

User "bob@example.com" in "Acme Corp"
├── Is member of: "Manager" role (role_type=1)
└── Manager role has: ["manage_users", "view_reports"]

When Bob makes request:
├── Check bob is in acme_corp org
├── Fetch bob's roles
├── Check if required permission in any role
└── Allow/deny request
```

---

## Summary

The multi-organization system provides:

✅ **Complete Data Isolation** - Each org in separate schema
✅ **Token-Based Routing** - OrgId in JWT determines schema
✅ **Dynamic Schema Creation** - New orgs = new schemas
✅ **Role-Based Access** - Flexible permission system
✅ **Performance** - Indexes per schema, no cross-schema queries
✅ **Security** - Multiple layers of authorization checks
✅ **Scalability** - Schemas can be moved to different databases if needed
