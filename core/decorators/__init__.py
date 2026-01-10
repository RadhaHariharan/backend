from functools import wraps
from typing import List, Callable, Any
from sqlalchemy.ext.asyncio import AsyncSession
from api.deps import get_db
from core.middleware.auth_middleware import accessTokenData
from services.permission_service import PermissionService
from utils.response import HttpError


def require_permission(
    permissions: List[str],
    require_all: bool = False
) -> Callable:
    """
    Decorator to enforce permission checks on API route handlers
    
    Args:
        permissions: List of permission names required to access the route
        require_all: If True, user must have ALL permissions.
                    If False, user must have AT LEAST ONE permission.
    
    Usage Examples:
        @router.get("/admin/users")
        @require_permission(["read_users", "admin"], require_all=True)
        async def get_all_users(db: AsyncSession = Depends(get_db)):
            # Only users with BOTH "read_users" AND "admin" permissions
            ...
        
        @router.post("/posts")
        @require_permission(["create_posts", "create_comments"])
        async def create_post(db: AsyncSession = Depends(get_db)):
            # Only users with AT LEAST ONE of "create_posts" OR "create_comments"
            ...
    """
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # --- Extract db session from kwargs ---
            db = kwargs.get("db")
            if not db:
                # Try to find db in args (in case it's positional)
                for arg in args:
                    if isinstance(arg, AsyncSession):
                        db = arg
                        break
            
            if not db:
                raise HttpError(
                    status_code=500,
                    message="Database session not found",
                    error="INTERNAL_ERROR"
                )
            
            # --- Get token data from context ---
            token_data = accessTokenData.get()
            if not token_data or not token_data.get("sub"):
                raise HttpError(
                    status_code=401,
                    message="Unauthorized: User not authenticated",
                    error="UNAUTHORIZED"
                )
            
            # --- Check permissions ---
            permission_service = PermissionService(db=db, user_id=token_data.get("sub"))
            await permission_service.check_permissions(
                required_permissions=permissions,
                require_all=require_all
            )
            
            # --- Call the original function ---
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator
