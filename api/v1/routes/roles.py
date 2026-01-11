from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Optional

from api.deps import get_db
from repositories.role_repo import RoleRepository
from repositories.org_user_repo import OrgUserRepository
from models.role import Role
from utils.response import send_custom_response, HttpError
from utils.token_data import get_current_user_access_token

router = APIRouter(prefix="/roles", tags=["Roles"])


class CreateRoleRequest(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: List[str] = []


class RoleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    permissions: List[str]
    
    class Config:
        from_attributes = True


class AssignRoleRequest(BaseModel):
    user_id: str
    role_id: str


@router.post("/", response_model=RoleResponse, status_code=201)
async def create_role(
    payload: CreateRoleRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create new role in current organization"""
    token_data = get_current_user_access_token()
    user_id = token_data.get("sub")
    
    # Check if user is admin
    org_user_repo = OrgUserRepository(db)
    org_user = await org_user_repo.get_by_user_id(user_id)
    
    if not org_user or not org_user.is_admin:
        raise HttpError(403, "Insufficient permissions to manage roles", "INSUFFICIENT_PERMISSIONS")
    
    role_repo = RoleRepository(db)
    
    # Check if role name exists
    existing = await role_repo.get_by_name(payload.name)
    if existing:
        raise HttpError(400, f"Role '{payload.name}' already exists", "ROLE_EXISTS")
    
    role = Role(
        name=payload.name,
        description=payload.description,
        permissions=payload.permissions
    )
    
    created_role = await role_repo.create(role)
    
    return send_custom_response(
        {
            "id": str(created_role.id),
            "name": created_role.name,
            "description": created_role.description,
            "permissions": created_role.permissions
        },
        success_message="Role created successfully",
        status_code=201
    )


@router.get("/")
async def list_roles(db: AsyncSession = Depends(get_db)):
    """List all roles in current organization"""
    role_repo = RoleRepository(db)
    roles = await role_repo.list_all()
    
    return send_custom_response([
        {
            "id": str(role.id),
            "name": role.name,
            "description": role.description,
            "permissions": role.permissions
        }
        for role in roles
    ])


@router.post("/assign", status_code=200)
async def assign_role_to_user(
    payload: AssignRoleRequest,
    db: AsyncSession = Depends(get_db)
):
    """Assign role to user in current organization"""
    token_data = get_current_user_access_token()
    user_id = token_data.get("sub")
    
    # Check if current user is admin
    org_user_repo = OrgUserRepository(db)
    org_user = await org_user_repo.get_by_user_id(user_id)
    
    if not org_user or not org_user.is_admin:
        raise HttpError(403, "Insufficient permissions to assign roles", "INSUFFICIENT_PERMISSIONS")
    
    role_repo = RoleRepository(db)
    
    # Verify role exists
    role = await role_repo.get_by_id(payload.role_id)
    if not role:
        raise HttpError(404, "Role not found", "ROLE_NOT_FOUND")
    
    # Verify user exists in org
    target_user = await org_user_repo.get_by_user_id(payload.user_id)
    if not target_user:
        raise HttpError(404, "User not found in organization", "USER_NOT_FOUND")
    
    user_role = await role_repo.assign_role_to_user(payload.user_id, payload.role_id)
    
    return send_custom_response(
        {
            "id": str(user_role.id),
            "user_id": str(user_role.user_id),
            "role_id": str(user_role.role_id)
        },
        success_message="Role assigned successfully"
    )


@router.delete("/unassign")
async def remove_role_from_user(
    payload: AssignRoleRequest,
    db: AsyncSession = Depends(get_db)
):
    """Remove role from user in current organization"""
    token_data = get_current_user_access_token()
    user_id = token_data.get("sub")
    
    # Check if current user is admin
    org_user_repo = OrgUserRepository(db)
    org_user = await org_user_repo.get_by_user_id(user_id)
    
    if not org_user or not org_user.is_admin:
        raise HttpError(403, "Insufficient permissions to remove roles", "INSUFFICIENT_PERMISSIONS")
    
    role_repo = RoleRepository(db)
    
    await role_repo.remove_role_from_user(payload.user_id, payload.role_id)
    
    return send_custom_response(
        None,
        success_message="Role removed successfully"
    )


@router.get("/user/{user_id}")
async def get_user_roles(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all roles assigned to a user in current organization"""
    role_repo = RoleRepository(db)
    roles = await role_repo.get_user_roles(user_id)
    
    return send_custom_response([
        {
            "id": str(role.id),
            "name": role.name,
            "description": role.description,
            "permissions": role.permissions
        }
        for role in roles
    ])
