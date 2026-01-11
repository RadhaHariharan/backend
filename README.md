# FastAPI Multi-Tenant Organization System

A complete multi-tenant application backend built with **FastAPI**, **SQLAlchemy**, and **PostgreSQL**. Supports flexible user management with dynamic organization creation and role-based access control.

---

## 🚀 Project Setup

### Prerequisites
- **Python 3.11+** (3.13 recommended)
- **PostgreSQL 12+**
- `pip` for package management

### 1. Create Virtual Environment

```bash
# Create a new virtual environment
python3 -m venv fastapienv

# Activate it (macOS/Linux)
source fastapienv/bin/activate

# Or on Windows PowerShell
.\fastapienv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

**To generate `requirements.txt` from your current environment:**

```bash
pip freeze > requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_password
DB_NAME=your_database

# Security
JWT_SECRET_KEY=your-super-secret-key-change-in-production
JWT_ALGORITHM=HS256

# Environment
ENVIRONMENT=development
```

### 4. Initialize Database

```bash
# Using SQL script (fastest)
psql -U postgres -d your_database -f scripts/init_schemas.sql

# OR using Alembic migrations
alembic upgrade head
```

### 5. Run the Application

```bash
# Development with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Visit `http://localhost:8000/docs` for interactive API documentation.

---

## 🏗️ Architecture

### Database Schema

**Public Schema** (Global):
```
users
├── id, first_name, last_name, email, password_hash
├── status, created_at, updated_at
└── Indexes: email, email+status

organizations
├── id, name, slug, description, owner_id
├── status, created_at, updated_at
└── Indexes: slug, owner_id, slug+status
```

**Tenant Schemas** (One per Organization):
```
Schema name: {organization_uuid_with_underscores}

org_users (per-organization members)
├── id, user_id (FK to public.users), email, first_name, last_name
├── role_type (0=member, 1=admin, 2=owner)
├── status, joined_at, updated_at
└── Unique: user_id (one per user per org)

roles (organization-specific roles)
├── id, name, description
├── permissions (PostgreSQL array)
└── created_at, updated_at

user_org_roles (user-role assignments)
├── id, user_id, role_id, assigned_at
└── Unique: user_id + role_id
```

### Request Flow

```
Request → AuthMiddleware
    ↓
  (Validate JWT, set accessTokenData)
    ↓
TenantMiddleware
    ↓
  (Extract orgId, fetch org, set currentOrg context)
    ↓
Route Handler
    ↓
  (Use get_db() for tenant schema OR get_public_db())
    ↓
Database Query
    ↓
Response
```

### Token Evolution

**User Login (No Organization)**:
```json
{
  "sub": "user-uuid",
  "email": "user@example.com",
  "exp": 1234567890
}
```

**After Switching to Organization**:
```json
{
  "sub": "user-uuid",
  "email": "user@example.com",
  "orgId": "org-uuid",
  "exp": 1234567890
}
```

---

## 📁 Project Structure

```
backend/
├── main.py                           # FastAPI app entry point
│
├── api/
│   ├── deps.py                      # Dependency injection (db functions)
│   └── v1/
│       └── routes/
│           ├── auth.py              # Authentication endpoints
│           ├── organizations.py      # Organization endpoints
│           └── roles.py              # Role management endpoints
│
├── models/
│   ├── user.py                      # User model (public schema)
│   ├── organization.py               # Organization model
│   ├── org_user.py                   # OrgUser model (tenant schema)
│   ├── role.py                       # Role model (tenant schema)
│   └── user_org_role.py              # UserOrgRole model (tenant schema)
│
├── repositories/
│   ├── user_repo.py                 # User data access
│   ├── organization_repo.py          # Organization data access
│   ├── org_user_repo.py              # OrgUser data access (tenant)
│   └── role_repo.py                  # Role data access (tenant)
│
├── services/
│   ├── auth_service.py              # Authentication business logic
│   ├── organization_service.py       # Organization business logic
│   └── permission_service.py         # Permission/role logic
│
├── core/
│   ├── config.py                    # Configuration from env vars
│   ├── database.py                  # Database connection & schema mgmt
│   ├── security.py                  # Password hashing, token creation
│   ├── exception_handlers.py         # Global error handlers
│   ├── logger.py                    # Logging setup
│   └── middleware/
│       ├── auth_middleware.py       # JWT validation
│       └── tenant_middleware.py     # Tenant context setup
│
├── schemas/
│   └── auth.py                      # Request/response schemas
│
├── utils/
│   ├── response.py                  # Standard response format
│   ├── token_data.py                # Token parsing utilities
│   └── date_time.py                 # Date/time utilities
│
├── migrations/                       # Alembic migration files
├── scripts/
│   └── init_schemas.sql             # Database initialization script
│
├── requirements.txt                 # Python dependencies
├── .env.example                     # Example environment variables
└── README.md                        # This file
```

---

## 📊 Environment Variables Reference

```env
# PostgreSQL Configuration
DB_HOST=localhost          # Database host
DB_PORT=5432             # Database port
DB_USER=postgres         # Database user
DB_PASSWORD=password     # Database password
DB_NAME=your_database    # Database name

# Security
JWT_SECRET_KEY=secret    # JWT signing key (change in production!)
JWT_ALGORITHM=HS256      # JWT algorithm

# Runtime
ENVIRONMENT=development  # development or production
```
