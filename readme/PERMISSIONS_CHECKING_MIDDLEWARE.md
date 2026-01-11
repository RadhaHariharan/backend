# Permissions Checking Middleware - In Depth Guide

This document provides a comprehensive explanation of how the permission checking system works in the multi-tenant architecture, including middleware implementation, permission models, and security guarantees.

## Table of Contents
1. [Overview](#overview)
2. [Middleware Stack](#middleware-stack)
3. [Authentication Middleware](#authentication-middleware)
4. [Tenant Middleware](#tenant-middleware)
5. [Permission Checking](#permission-checking)
6. [Role-Based Access Control (RBAC)](#role-based-access-control-rbac)
7. [Implementation Details](#implementation-details)
8. [Request Flow Examples](#request-flow-examples)
9. [Security Considerations](#security-considerations)

---

## Overview

The permission system is built on **three layers**:

```
Layer 3: Route-Level Checks
         (Check user has specific permission)
         ↑
Layer 2: Tenant Middleware
         (Verify user is in organization)
         ↑
Layer 1: Auth Middleware
         (Validate JWT token)
```

Each layer builds on the previous, ensuring secure, isolated access to organization data.

---

## Middleware Stack

### Middleware Execution Order

```python
# In main.py
app = FastAPI()

# Order matters! Middleware executes in REVERSE order
app.add_middleware(TenantMiddleware)   # Executes 2nd
app.add_middleware(AuthMiddleware)     # Executes 1st (outermost)

# Request flow:
Request
  ↓
AuthMiddleware    ← Validates JWT, extracts token data
  ↓
TenantMiddleware  ← Fetches org context, sets up schema
  ↓
Route Handler     ← Executes with pre-configured context
  ↓
Response
```

### Middleware Scope

**Which routes require middleware?**

| Route | Auth Required | Org Required |
|-------|---------------|--------------|
| `/api/v1/auth/register` | ❌ No | ❌ No |
| `/api/v1/auth/login` | ❌ No | ❌ No |
| `/api/v1/organizations` (create) | ✅ Yes | ❌ No |
| `/api/v1/organizations/my-organizations` | ✅ Yes | ❌ No |
| `/api/v1/organizations/switch/{org_id}` | ✅ Yes | ❌ No |
| `/api/v1/roles` (any operation) | ✅ Yes | ✅ Yes |
| `/api/v1/organizations/{org_id}` | ✅ Yes | ✅ Maybe |

---

## Authentication Middleware

### Purpose

Validate JWT token and extract user identity.

### Implementation

```python
# In core/middleware/auth_middleware.py

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            # Step 1: Extract token from Authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                raise HTTPException(status_code=401, detail="Missing token")
            
            # Step 2: Parse "Bearer <token>"
            scheme, token = auth_header.split()
            if scheme.lower() != "bearer":
                raise HTTPException(status_code=401, detail="Invalid scheme")
            
            # Step 3: Decode and validate JWT
            payload = jwt.decode(
                token,
                JWT_SECRET_KEY,
                algorithms=["HS256"]
            )
            
            # Step 4: Extract claims
            user_id = payload.get("sub")
            email = payload.get("email")
            org_id = payload.get("orgId")  # May be None
            
            if not user_id or not email:
                raise HTTPException(status_code=401, detail="Invalid token")
            
            # Step 5: Create token data object
            token_data = TokenData(
                user_id=UUID(user_id),
                email=email,
                org_id=UUID(org_id) if org_id else None
            )
            
            # Step 6: Store in request scope for later access
            request.scope["token_data"] = token_data
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
        except Exception as e:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Step 7: Proceed to next middleware/handler
        return await call_next(request)
```

### What It Validates

✅ Token format (Bearer scheme)
✅ JWT signature (matches JWT_SECRET_KEY)
✅ Token expiration
✅ Required claims present (sub, email)

### What It Doesn't Validate

❌ Whether user still exists in database
❌ Whether organization exists
❌ Whether user is member of organization
❌ Whether user has permission for action

---

## Tenant Middleware

### Purpose

Establish organization context and prepare database session for org-specific queries.

### Implementation

```python
# In core/middleware/tenant_middleware.py

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Step 1: Get token data from AuthMiddleware
        token_data = request.scope.get("token_data")
        
        # Step 2: Check if request requires organization context
        if self.requires_org_context(request.url.path):
            if not token_data or not token_data.org_id:
                # Some endpoints require orgId in token
                raise HTTPException(
                    status_code=403,
                    detail="ORG_CONTEXT_MISSING"
                )
            
            # Step 3: Fetch organization from public schema
            org_db = SessionLocal()  # Public schema session
            organization = org_db.query(Organization).filter(
                Organization.id == token_data.org_id
            ).first()
            
            if not organization:
                raise HTTPException(
                    status_code=404,
                    detail="Organization not found"
                )
            
            # Step 4: Verify user is member of organization
            org_specific_db = get_db(organization.id)  # Org schema session
            org_user = org_specific_db.query(OrgUser).filter(
                OrgUser.user_id == token_data.user_id
            ).first()
            
            if not org_user:
                raise HTTPException(
                    status_code=403,
                    detail="NOT_ORG_MEMBER"
                )
            
            # Step 5: Store organization context in request
            request.scope["current_org"] = organization
            request.scope["current_org_user"] = org_user
            request.scope["org_db"] = org_specific_db
        
        # Step 6: Proceed to route handler
        return await call_next(request)
    
    def requires_org_context(self, path: str) -> bool:
        """
        Determine if request needs organization context.
        Paths starting with /api/v1/roles always need org context.
        Other paths may vary.
        """
        org_required_prefixes = [
            "/api/v1/roles",
        ]
        return any(path.startswith(prefix) for prefix in org_required_prefixes)
```

### What It Validates

✅ Organization exists in database
✅ Organization schema exists
✅ User is member of organization (in org_users)
✅ Sets up database session with correct search_path

### What It Does

🔧 Fetches organization details
🔧 Fetches user's org membership
🔧 Sets database search_path to org schema
🔧 Injects org context into request

---

## Permission Checking

### Permission Model

Permissions are defined at **role level**:

```python
# In models/role.py
class Role(Base):
    __tablename__ = "roles"
    __table_args__ = ({"schema": "<org_schema>"},)
    
    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str]
    description: Mapped[Optional[str]]
    permissions: Mapped[List[str]] = mapped_column(
        PostgreSQL.ARRAY(String),
        default=list
    )  # List of permission strings

# Example roles in organization schema:
# Role 1: Owner
#   permissions = ["admin", "manage_users", "manage_roles", "delete_org"]
#
# Role 2: Manager
#   permissions = ["manage_users", "view_reports"]
#
# Role 3: Member
#   permissions = ["view_reports"]
```

### Permission Checking Function

```python
# In core/security.py or utils/

async def check_permission(
    request: Request,
    required_permission: str
) -> bool:
    """
    Check if current user has required permission in their organization.
    """
    # Step 1: Get org context from middleware
    current_org = request.scope.get("current_org")
    token_data = request.scope.get("token_data")
    
    if not current_org or not token_data:
        return False
    
    # Step 2: Get org-specific database session
    org_db = get_db(current_org.id)
    
    # Step 3: Get user's org membership
    org_user = org_db.query(OrgUser).filter(
        OrgUser.user_id == token_data.user_id
    ).first()
    
    if not org_user:
        return False
    
    # Step 4: Get user's roles in this org
    user_roles = org_db.query(Role).join(
        UserOrgRole,
        Role.id == UserOrgRole.role_id
    ).filter(
        UserOrgRole.user_id == token_data.user_id
    ).all()
    
    # Step 5: Check if any role has required permission
    for role in user_roles:
        if required_permission in role.permissions:
            return True
    
    # Step 6: Return result
    return False


# Usage in route handler:
@router.post("/api/v1/roles")
async def create_role(
    request: Request,
    role_data: RoleCreate
):
    # Check permission before processing
    if not await check_permission(request, "manage_roles"):
        raise HTTPException(
            status_code=403,
            detail="PERMISSION_DENIED"
        )
    
    # Proceed with role creation...
```

---

## Role-Based Access Control (RBAC)

### User → Roles → Permissions Mapping

```
Organization "Acme Corp"
│
├── User: alice@example.com
│   └── Roles:
│       ├── Owner (permissions: [admin, manage_users, manage_roles, delete_org])
│       └── Manager (permissions: [manage_users, view_reports])
│
├── User: bob@example.com
│   └── Roles:
│       └── Manager (permissions: [manage_users, view_reports])
│
└── User: charlie@example.com
    └── Roles:
        └── Member (permissions: [view_reports])
```

### Database Representation

**org_users table:**
```
id              | user_id  | email              | role_type
─────────────────────────────────────────────────────────
uuid-1          | alice-id | alice@example.com  | 2 (owner)
uuid-2          | bob-id   | bob@example.com    | 1 (admin)
uuid-3          | charlie-id | charlie@example.com | 0 (member)
```

**roles table:**
```
id              | name     | permissions
──────────────────────────────────────────────────────
role-owner      | Owner    | [admin, manage_users, manage_roles, delete_org]
role-manager    | Manager  | [manage_users, view_reports]
role-member     | Member   | [view_reports]
```

**user_org_roles table:**
```
id    | user_id  | role_id
──────────────────────────────
ur-1  | alice-id | role-owner
ur-2  | alice-id | role-manager
ur-3  | bob-id   | role-manager
ur-4  | charlie-id | role-member
```

### Query to Check Permission

```sql
-- Check if alice has "manage_users" permission in Acme Corp
SELECT r.permissions
FROM user_org_roles uor
JOIN roles r ON uor.role_id = r.id
WHERE uor.user_id = 'alice-uuid'
AND r.permissions @> ARRAY['manage_users']
LIMIT 1;

-- Result: 
-- [admin, manage_users, manage_roles, delete_org]
-- Therefore: alice HAS permission
```

---

## Implementation Details

### 1. Dependency Injection Pattern

```python
# In api/deps.py

async def get_current_user(
    request: Request
) -> TokenData:
    """Extract authenticated user from request"""
    token_data = request.scope.get("token_data")
    if not token_data:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return token_data


async def get_current_org(
    request: Request
) -> Organization:
    """Extract current organization from request"""
    org = request.scope.get("current_org")
    if not org:
        raise HTTPException(status_code=403, detail="ORG_CONTEXT_MISSING")
    return org


async def get_org_user(
    request: Request
) -> OrgUser:
    """Extract current user's org membership"""
    org_user = request.scope.get("current_org_user")
    if not org_user:
        raise HTTPException(status_code=403, detail="NOT_ORG_MEMBER")
    return org_user


async def get_db(org_id: UUID) -> AsyncSession:
    """Get database session with correct schema"""
    session = SessionLocal()
    org = session.query(Organization).filter(
        Organization.id == org_id
    ).first()
    session.execute(f"SET search_path TO '{org.schema_name}', 'public'")
    return session
```

### 2. Route Handler with Dependency Injection

```python
# In api/v1/routes/roles.py

@router.post("/api/v1/roles")
async def create_role(
    request: Request,
    current_user: TokenData = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    org_user: OrgUser = Depends(get_org_user),
    role_data: RoleCreate
):
    """
    Create a new role in the organization.
    Only admins and owners can create roles.
    """
    
    # Step 1: Check user's role_type (built-in permission)
    if org_user.role_type < 1:  # 0=member, 1=admin, 2=owner
        raise HTTPException(
            status_code=403,
            detail="INSUFFICIENT_PERMISSIONS"
        )
    
    # Step 2: Get database session (already has correct schema)
    db = request.scope.get("org_db")
    
    # Step 3: Create role
    new_role = Role(
        id=uuid4(),
        name=role_data.name,
        description=role_data.description,
        permissions=role_data.permissions
    )
    db.add(new_role)
    db.commit()
    
    # Step 4: Return response
    return {
        "status": "success",
        "result": new_role.to_dict()
    }
```

### 3. Custom Permission Decorator

```python
# In core/decorators/

from functools import wraps

def require_permission(permission: str):
    """Decorator to enforce permission checks"""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Check permission before executing handler
            has_permission = await check_permission(request, permission)
            if not has_permission:
                raise HTTPException(
                    status_code=403,
                    detail="PERMISSION_DENIED"
                )
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


# Usage:
@router.post("/api/v1/roles")
@require_permission("manage_roles")
async def create_role(request: Request, role_data: RoleCreate):
    """This endpoint requires manage_roles permission"""
    # Implementation...
```

---

## Request Flow Examples

### Example 1: Creating a Role (Permission Check)

```
1. Client sends request:
   POST /api/v1/roles
   Authorization: Bearer <token_with_orgId>
   Body: { name: "Manager", permissions: [...] }

2. Request arrives at FastAPI:
   ├── AuthMiddleware
   │  ├── Extracts token from header
   │  ├── Validates JWT signature
   │  ├── Decodes payload:
   │  │  {
   │  │    "sub": "user-uuid-1",
   │  │    "email": "alice@example.com",
   │  │    "orgId": "org-uuid-1",
   │  │    "exp": 1234567890
   │  │  }
   │  ├── Creates TokenData object
   │  └── Stores in request.scope["token_data"]
   │
   ├── TenantMiddleware
   │  ├── Retrieves token_data (user_id, email, org_id)
   │  ├── Checks if route requires org context: YES
   │  ├── Fetches Organization from public.organizations
   │  │  └── SELECT * FROM organizations WHERE id = org-uuid-1
   │  ├── Creates session with org schema
   │  │  └── SET search_path TO 'org_schema_uuid, public'
   │  ├── Verifies user is org member
   │  │  └── SELECT * FROM org_users WHERE user_id = user-uuid-1
   │  └── Stores context in request.scope

3. Route handler executes:
   @router.post("/api/v1/roles")
   async def create_role(
       request: Request,
       current_user: TokenData = Depends(get_current_user),
       current_org: Organization = Depends(get_current_org)
   ):

4. Permission check:
   ├── Get user's roles in org
   │  └── SELECT r.* FROM roles r
   │      JOIN user_org_roles uor ON r.id = uor.role_id
   │      WHERE uor.user_id = user-uuid-1
   │      └── Result: [Owner, Manager] roles
   │
   ├── Check if "manage_roles" in any role's permissions
   │  └── Owner.permissions = [admin, manage_roles, ...]
   │      └── Found! "manage_roles" is present
   │
   └── Permission granted: CONTINUE

5. Create role in database:
   INSERT INTO roles (id, name, permissions, ...)
   VALUES (uuid, "Manager", [...], ...)
   └── Query executes in org schema (via search_path)

6. Return response:
   {
     "status": "success",
     "result": { id, name, permissions }
   }
```

### Example 2: Unauthorized Access (Permission Denied)

```
1. Client sends request:
   POST /api/v1/roles
   Authorization: Bearer <token_with_orgId>
   Body: { name: "Restricted", permissions: [...] }
   
   Token user: charlie (with "Member" role only)

2. Middleware processing (same as Example 1):
   ├── AuthMiddleware: validates token ✅
   ├── TenantMiddleware: verifies org membership ✅
   └── Sets up context

3. Permission check in route handler:
   ├── Get charlie's roles in org
   │  └── SELECT r.* FROM roles r
   │      JOIN user_org_roles uor ON r.id = uor.role_id
   │      WHERE uor.user_id = charlie-uuid
   │      └── Result: [Member] role only
   │
   ├── Check if "manage_roles" in [Member]
   │  └── Member.permissions = [view_reports]
   │      └── NOT FOUND! "manage_roles" not present
   │
   └── Permission denied: STOP

4. Return error response:
   HTTP 403 Forbidden
   {
     "status": "error",
     "detail": "PERMISSION_DENIED"
   }
```

### Example 3: Missing Organization Context

```
1. Client sends request:
   POST /api/v1/roles
   Authorization: Bearer <token_WITHOUT_orgId>
   Body: { name: "Role", permissions: [...] }
   
   Token only has: { sub, email } (no orgId)

2. AuthMiddleware:
   ├── Validates JWT ✅
   ├── Extracts token_data
   │  └── org_id = None
   └── Stores in request.scope

3. TenantMiddleware:
   ├── Checks if route requires org context
   │  └── /api/v1/roles → YES, requires org
   │
   ├── Checks if token has org_id
   │  └── token_data.org_id = None
   │
   └── Permission denied: STOP

4. Return error response:
   HTTP 403 Forbidden
   {
     "status": "error",
     "detail": "ORG_CONTEXT_MISSING"
   }

5. Fix: User must switch to organization first:
   POST /api/v1/organizations/switch/{org_id}
   └── Get new token WITH orgId in it
   └── Then use that token for role endpoints
```

---

## Security Considerations

### 1. Token Scope Isolation

**Principle:** Tokens are scoped to either:
- No organization (can manage orgs, switch orgs)
- One specific organization (can access org data)

**Implementation:**
```python
# A user cannot use an Acme Corp token to access TechCorp data
# even if they're a member of both orgs

Token 1 (orgId=acme): Can only query acme schema
Token 2 (orgId=techcorp): Can only query techcorp schema

If client tries to use Token 1 on TechCorp data:
└── TenantMiddleware checks: request orgId != token orgId
└── Returns 403 Forbidden
```

### 2. Database-Level Isolation

**Principle:** Even if middleware is bypassed, database schema prevents access

**Implementation:**
```sql
-- PostgreSQL schema isolation
CREATE SCHEMA acme_corp_uuid;
CREATE SCHEMA techcorp_uuid;

-- Table access is schema-qualified:
SELECT * FROM acme_corp_uuid.roles;
SELECT * FROM techcorp_uuid.roles;

-- Even if application code tried:
SELECT * FROM roles;  -- Would fail (schema not found)
```

### 3. JWT Signature Verification

**Principle:** Tokens cannot be forged without the secret key

**Implementation:**
```python
# During validation:
payload = jwt.decode(
    token,
    JWT_SECRET_KEY,
    algorithms=["HS256"]
)

# If token was modified:
└── Signature verification fails
└── jwt.InvalidTokenError raised
└── Returns 401 Unauthorized

# Security: JWT_SECRET_KEY must never be exposed
```

### 4. Role-Based Permission Matrix

**Principle:** Permissions are checked at every operation

**Implementation:**
```
Operation                    | Required Permission | Default Roles
─────────────────────────────────────────────────────────────────
Create role                  | manage_roles       | Owner, Admin
Delete role                  | manage_roles       | Owner, Admin
Assign role to user          | manage_users       | Owner, Admin
Delete organization          | delete_org         | Owner
View organization members    | view_users         | Owner, Admin, Manager
View reports                 | view_reports       | Owner, Admin, Manager, Member
```

### 5. Time-Based Token Expiration

**Principle:** Tokens expire after a fixed period

**Implementation:**
```python
from datetime import datetime, timedelta

def create_access_token(data: dict):
    to_encode = data.copy()
    
    # Token expires in 1 hour
    expire = datetime.utcnow() + timedelta(hours=1)
    to_encode["exp"] = expire
    
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm="HS256")

# Expired tokens are rejected:
try:
    payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
except jwt.ExpiredSignatureError:
    raise HTTPException(status_code=401, detail="Token expired")
    # User must login again or use refresh token
```

---

## Common Security Patterns

### Pattern 1: Admin-Only Operations

```python
@router.delete("/api/v1/organizations/{org_id}")
async def delete_organization(
    org_id: UUID,
    current_org_user: OrgUser = Depends(get_org_user)
):
    """Only organization owner can delete org"""
    
    if current_org_user.role_type != 2:  # 2 = owner
        raise HTTPException(status_code=403, detail="OWNER_ONLY")
    
    # Delete organization...
```

### Pattern 2: Custom Permission Check

```python
@router.post("/api/v1/reports/export")
async def export_report(
    request: Request,
    current_user: TokenData = Depends(get_current_user)
):
    """Check custom permission before exporting"""
    
    has_permission = await check_permission(
        request,
        "export_reports"
    )
    
    if not has_permission:
        raise HTTPException(status_code=403)
    
    # Export report...
```

### Pattern 3: Audit Logging

```python
@router.post("/api/v1/roles")
async def create_role(
    request: Request,
    current_user: TokenData = Depends(get_current_user),
    role_data: RoleCreate
):
    """Log who created what role"""
    
    # ... create role ...
    
    # Log the action
    audit_log = AuditLog(
        user_id=current_user.user_id,
        org_id=current_org.id,
        action="CREATE_ROLE",
        resource_id=new_role.id,
        timestamp=datetime.utcnow()
    )
    db.add(audit_log)
    db.commit()
```

---

## Summary

The permission checking system provides:

✅ **Multi-Layer Security**
   - JWT validation (Layer 1)
   - Organization membership (Layer 2)
   - Permission checking (Layer 3)

✅ **Complete Isolation**
   - Each request scoped to one organization
   - Database-level schema separation
   - Token-based context

✅ **Flexible RBAC**
   - Custom roles per organization
   - Granular permissions
   - Easy to extend

✅ **Audit Trail**
   - All access logged via token data
   - Request context includes user and org

✅ **High Performance**
   - Minimal database queries
   - Schema-based query routing
   - Connection pooling

✅ **Developer Friendly**
   - Dependency injection pattern
   - Decorator-based permission checks
   - Clear error messages
