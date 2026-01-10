# Permission Check Wrapper - Setup & Usage Guide

## Overview
The permission check wrapper is a decorator-based system to enforce permission checks on API routes. It uses your existing JWT authentication via `contextvars` to retrieve user information.

**How it works:**
1. `AuthMiddleware` decodes JWT and stores token data in `accessTokenData` context
2. `@require_permission` decorator gets user_id from token context
3. `PermissionService` queries database to fetch user and check permissions
4. Route is executed or error is thrown

---

## What Was Created

### 1. **PermissionService** - `services/permission_service.py`
- Takes `db` session and `user_id` from token
- Fetches user from database
- Validates permissions
- Throws `HttpError` on permission denial

### 2. **require_permission Decorator** - `core/decorators/__init__.py`
- Simple decorator to wrap your routes
- Extracts token data from context
- Calls PermissionService before route execution
- No `request` parameter needed in your route handlers

---

## Step 1: Customize Permission Logic

Edit [services/permission_service.py](services/permission_service.py) and implement `_get_user_permissions()` based on your User model:

**Example 1: Using roles with permissions**
```python
async def _get_user_permissions(self) -> List[str]:
    """Get user permissions from roles"""
    if not self.user:
        return []
    
    permissions = []
    if hasattr(self.user, 'roles') and self.user.roles:
        for role in self.user.roles:
            if hasattr(role, 'permissions'):
                permissions.extend([p.name for p in role.permissions])
    
    return list(set(permissions))
```

**Example 2: Direct user permissions**
```python
async def _get_user_permissions(self) -> List[str]:
    """Get user permissions directly"""
    if not self.user:
        return []
    
    permissions = []
    if hasattr(self.user, 'permissions') and self.user.permissions:
        permissions = [p.name for p in self.user.permissions]
    
    return permissions
```

**Example 3: Status-based (like your User model with status column)**
```python
async def _get_user_permissions(self) -> List[str]:
    """Get permissions based on user status"""
    if not self.user or self.user.status == 0:
        return []  # Inactive user has no permissions
    
    # You can check user attributes, roles, flags, etc.
    permissions = ['user']  # All active users have 'user' permission
    
    # Add more specific permissions based on your schema
    if hasattr(self.user, 'is_admin') and self.user.is_admin:
        permissions.append('admin')
    
    return permissions
```

---

## Step 2: Use the Decorator on Your Routes

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from api.deps import get_db
from core.decorators import require_permission

router = APIRouter(prefix="/api/v1/users", tags=["Users"])

# Require at least ONE permission
@router.post("/")
@require_permission(["create_users", "admin"])
async def create_user(payload: CreateUserRequest, db: AsyncSession = Depends(get_db)):
    """Create user - needs create_users OR admin"""
    # Your code here
    pass

# Require ALL permissions
@router.delete("/{user_id}")
@require_permission(["delete_users", "admin"], require_all=True)
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db)):
    """Delete user - needs BOTH delete_users AND admin"""
    # Your code here
    pass

# Single permission
@router.get("/admin")
@require_permission(["admin"])
async def admin_dashboard(db: AsyncSession = Depends(get_db)):
    """Admin only"""
    pass
```

**Key points:**
- ✅ NO `request` parameter needed
- ✅ `@require_permission` goes AFTER `@router.post/get/etc`
- ✅ Use `db: AsyncSession = Depends(get_db)` normally
- ✅ Decorator handles user lookup and permission checking

---

## API Reference

```python
@require_permission(
    permissions: List[str],      # Permission names to check
    require_all: bool = False     # True = ALL required, False = AT LEAST ONE
)
```

**Parameters:**
- `permissions`: List of permission string names (e.g., `["read_users", "admin"]`)
- `require_all` (optional): 
  - `False` (default): User needs at least one permission
  - `True`: User needs all permissions

---

## Error Responses

All errors return your standard `HttpError` format:

### 401 - Unauthorized (No Token)
```json
{
  "message": "Unauthorized: User not authenticated",
  "statusCode": 401,
  "error": "UNAUTHORIZED"
}
```

### 401 - User Not Found
```json
{
  "message": "Unauthorized: User not found",
  "statusCode": 401,
  "error": "USER_NOT_FOUND"
}
```

### 403 - Insufficient Permissions (require_all=False)
```json
{
  "message": "Forbidden: You must have at least one of these permissions: create_posts, admin",
  "statusCode": 403,
  "error": "INSUFFICIENT_PERMISSIONS"
}
```

### 403 - Insufficient Permissions (require_all=True)
```json
{
  "message": "Forbidden: You must have all of these permissions: delete_posts, admin",
  "statusCode": 403,
  "error": "INSUFFICIENT_PERMISSIONS"
}
```

---

## Real-World Examples

### User Management Routes

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from api.deps import get_db
from core.decorators import require_permission

router = APIRouter(prefix="/api/v1/users", tags=["Users"])

@router.get("/")
@require_permission(["read_users", "admin"])
async def list_users(db: AsyncSession = Depends(get_db)):
    """List users - read_users OR admin"""
    pass

@router.post("/")
@require_permission(["create_users"])
async def create_user(payload: CreateUserRequest, db: AsyncSession = Depends(get_db)):
    """Create user - create_users required"""
    pass

@router.put("/{user_id}")
@require_permission(["edit_users"])
async def update_user(user_id: str, payload: UpdateUserRequest, db: AsyncSession = Depends(get_db)):
    """Update user - edit_users required"""
    pass

@router.delete("/{user_id}")
@require_permission(["delete_users", "admin"], require_all=True)
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db)):
    """Delete user - needs BOTH delete_users AND admin"""
    pass
```

### Post/Content Routes

```python
@router.post("/posts")
@require_permission(["create_posts"])
async def create_post(payload: CreatePostRequest, db: AsyncSession = Depends(get_db)):
    """Create post - create_posts required"""
    pass

@router.put("/posts/{post_id}")
@require_permission(["edit_own_posts", "edit_any_posts"], require_all=False)
async def edit_post(post_id: str, payload: UpdatePostRequest, db: AsyncSession = Depends(get_db)):
    """Edit post - edit_own_posts OR edit_any_posts"""
    pass

@router.delete("/posts/{post_id}")
@require_permission(["delete_posts"])
async def delete_post(post_id: str, db: AsyncSession = Depends(get_db)):
    """Delete post - delete_posts required"""
    pass
```

---

## Integration with Existing Code

The decorator integrates seamlessly with:
- ✅ Your `AuthMiddleware` (uses `accessTokenData` context automatically)
- ✅ Your `get_db` dependency
- ✅ Your `HttpError` exception class
- ✅ Your existing error handling in `main.py`

**No changes needed to middleware or other code!**

---

## Best Practices

1. **Descriptive permission names**: `read_users`, `edit_own_posts`, `delete_any_posts`
2. **Place decorator after route definition**:
   ```python
   @router.post("/")      # ← First
   @require_permission(["create"])  # ← Then decorator
   async def my_route():  # ← Then function
   ```
3. **Document in docstring**: State permission requirements
4. **Test thoroughly** before deployment
5. **Avoid nested decorators**: Use `require_all` parameter instead

---

## Folder Structure

```
backend/
├── core/
│   ├── decorators/
│   │   └── __init__.py              # ← Decorator here
│   ├── middleware/
│   │   └── auth_middleware.py       # ← Sets context
│   └── ...
├── services/
│   ├── permission_service.py        # ← Customize this
│   └── ...
└── ...
```

---

## Summary

✅ **Created:** `core/decorators/__init__.py` with `@require_permission`  
✅ **Created:** `services/permission_service.py` with permission logic  
✅ **To do:** Customize `_get_user_permissions()` in `PermissionService`  
✅ **To do:** Add `@require_permission` decorator to your routes  

That's it! Your permission system is ready to use! 🚀
