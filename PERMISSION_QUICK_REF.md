# Permission Decorator - Quick Reference

## 📍 Location
- **Decorator**: `core/decorators/__init__.py`
- **Service**: `services/permission_service.py`
- **Middleware**: `core/middleware/auth_middleware.py` (already exists)

## 🔧 Setup (3 steps)

### 1. Edit PermissionService
File: `services/permission_service.py`

Update `_get_user_permissions()` method:
```python
async def _get_user_permissions(self) -> List[str]:
    if not self.user:
        return []
    
    permissions = []
    # TODO: Add your logic here to get permissions from user model
    # Example: if hasattr(self.user, 'is_admin') and self.user.is_admin:
    #             permissions.append('admin')
    return permissions
```

### 2. Import Decorator
```python
from core.decorators import require_permission
```

### 3. Add to Routes
```python
@router.post("/users")
@require_permission(["create_users", "admin"])
async def create_user(payload: ..., db: AsyncSession = Depends(get_db)):
    pass
```

---

## 📖 Usage

### At Least One Permission (Default)
```python
@require_permission(["read_users", "admin"])
async def list_users(db: AsyncSession = Depends(get_db)):
    """User needs read_users OR admin"""
    pass
```

### All Permissions Required
```python
@require_permission(["delete_users", "admin"], require_all=True)
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db)):
    """User needs BOTH delete_users AND admin"""
    pass
```

### Single Permission
```python
@require_permission(["admin"])
async def admin_only(db: AsyncSession = Depends(get_db)):
    pass
```

---

## ⚡ Key Points

✅ **No `request` parameter** - Just use `db` normally  
✅ **Token extracted automatically** - From `accessTokenData` context  
✅ **User fetched from DB** - By `PermissionService`  
✅ **Errors thrown automatically** - HttpError with proper status codes  
✅ **Works with existing auth** - No middleware changes needed  

---

## 🔄 How It Works

```
Request comes in
    ↓
AuthMiddleware decodes JWT → sets accessTokenData context
    ↓
Your decorated route is called
    ↓
@require_permission decorator intercepts
    ↓
Gets token data from context → extracts user_id
    ↓
PermissionService fetches user from DB
    ↓
PermissionService._get_user_permissions() called
    ↓
Permissions checked (AND/OR logic)
    ↓
If valid → route executes
If invalid → HttpError(403) thrown
```

---

## 🚨 Error Responses

| Scenario | Status | Error Code |
|----------|--------|-----------|
| No token | 401 | `UNAUTHORIZED` |
| User not found | 401 | `USER_NOT_FOUND` |
| Missing permissions | 403 | `INSUFFICIENT_PERMISSIONS` |

---

## 💡 Examples

### User model with status column
```python
async def _get_user_permissions(self) -> List[str]:
    if not self.user or self.user.status == 0:
        return []
    
    permissions = ['user']
    
    # Check if admin somehow (add your logic)
    if hasattr(self.user, 'is_admin') and self.user.is_admin:
        permissions.append('admin')
    
    return permissions
```

### With roles relationship
```python
async def _get_user_permissions(self) -> List[str]:
    if not self.user:
        return []
    
    permissions = []
    if hasattr(self.user, 'roles'):
        for role in self.user.roles:
            if hasattr(role, 'permissions'):
                permissions.extend([p.name for p in role.permissions])
    
    return list(set(permissions))
```

---

## 📋 Complete Example Route File

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from api.deps import get_db
from core.decorators import require_permission
from utils.response import send_custom_response, HttpError

router = APIRouter(prefix="/api/v1/users", tags=["Users"])

# PUBLIC - In public_routes in main.py
@router.post("/login")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login - no permission needed"""
    return send_custom_response(tokens)

# PROTECTED - Requires permission
@router.get("/")
@require_permission(["read_users", "admin"])
async def list_users(db: AsyncSession = Depends(get_db)):
    """List users - read_users OR admin"""
    return send_custom_response(users)

# PROTECTED - Specific permission
@router.post("/")
@require_permission(["create_users"])
async def create_user(payload: CreateUserRequest, db: AsyncSession = Depends(get_db)):
    """Create user - create_users required"""
    return send_custom_response(new_user, status_code=201)

# PROTECTED - All permissions required
@router.delete("/{user_id}")
@require_permission(["delete_users", "admin"], require_all=True)
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db)):
    """Delete user - BOTH delete_users AND admin required"""
    return send_custom_response(message="Deleted")
```

---

## 🎯 Recommended Permission Names

### User Management
- `read_users` - View user list/details
- `create_users` - Create new users
- `edit_users` - Edit users
- `delete_users` - Delete users

### Admin
- `admin` - Full access
- `manage_roles` - Manage roles
- `manage_permissions` - Manage permissions

### Content
- `create_posts` - Create posts
- `edit_own_posts` - Edit own posts
- `edit_any_posts` - Edit any posts
- `delete_posts` - Delete posts

---

## ❓ FAQ

**Q: Where does `request.state.user` come from?**  
A: It doesn't! The decorator uses `accessTokenData` context from `AuthMiddleware` instead.

**Q: Do I need to modify AuthMiddleware?**  
A: No! It already stores token data in `accessTokenData` context.

**Q: Can I get the current user in my route?**  
A: Yes, call `PermissionService(db, user_id).user` if needed, or query it yourself.

**Q: What if user has no permissions table?**  
A: Customize `_get_user_permissions()` to return permissions based on user attributes/roles/whatever you have.

---

See [PERMISSION_SETUP.md](PERMISSION_SETUP.md) for detailed documentation.
