from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from repositories.user_repo import UserRepository
from utils.response import HttpError


class PermissionService:
    """
    Service to handle permission checking logic
    You can extend this with your custom permission validation
    """
    
    def __init__(self, db: AsyncSession, user_id: str):
        """
        Args:
            db: AsyncSession database session
            user_id: User ID from token payload (token_data['sub'])
        """
        self.db = db
        self.user_id = user_id
        self.user_repo = UserRepository(db)
        self.user = None
    
    async def check_permissions(
        self, 
        required_permissions: List[str], 
        require_all: bool = False
    ) -> bool:
        """
        Check if user has required permissions
        
        Args:
            required_permissions: List of permission names to check
            require_all: If True, user must have ALL permissions. 
                        If False, user must have AT LEAST ONE permission.
        
        Returns:
            bool: True if user has required permissions, False otherwise
        
        Raises:
            HttpError: If user is not found or doesn't have permissions
        """
        
        # --- Fetch user from database ---
        self.user = await self.user_repo.get_by_id(self.user_id)
        
        if not self.user:
            raise HttpError(
                status_code=401,
                message="Unauthorized: User not found",
                error="USER_NOT_FOUND"
            )
        
        # --- Get user permissions ---
        user_permissions = await self._get_user_permissions()
        
        if require_all:
            # --- User must have ALL required permissions ---
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
            # --- User must have AT LEAST ONE required permission ---
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
        Get list of permissions for the authenticated user
        
        CUSTOMIZE THIS METHOD BASED ON YOUR DATABASE STRUCTURE
        
        Example implementations:
        - Query user_roles table and get permissions from roles
        - Query user_permissions table directly
        - Check user attributes/flags
        
        Returns:
            List[str]: List of permission strings
        """
        
        # --- PLACEHOLDER: Implement based on your DB schema ---
        # Example 1 - Get from user roles:
        # permissions = []
        # if hasattr(self.user, 'roles') and self.user.roles:
        #     for role in self.user.roles:
        #         if hasattr(role, 'permissions'):
        #             permissions.extend([p.name for p in role.permissions])
        
        # Example 2 - Get from direct user permissions:
        # if hasattr(self.user, 'permissions') and self.user.permissions:
        #     permissions.extend([p.name for p in self.user.permissions])
        
        # Example 3 - Admin bypass:
        # if hasattr(self.user, 'is_admin') and self.user.is_admin:
        #     permissions.append('admin')
        
        # For now, return empty list (customize as needed)
        return []
