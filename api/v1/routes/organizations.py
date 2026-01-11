from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Optional

from api.deps import get_public_db
from services.organization_service import OrganizationService
from core.security import create_access_token, create_refresh_token
from utils.response import send_custom_response, HttpError
from utils.token_data import get_current_user_access_token

router = APIRouter(prefix="/organizations", tags=["Organizations"])


class CreateOrgRequest(BaseModel):
    name: str
    description: Optional[str] = None
    slug: Optional[str] = None


class OrgResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    owner_id: str
    status: int
    
    class Config:
        from_attributes = True


class SwitchOrgResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    organization: OrgResponse


@router.post("/", response_model=OrgResponse, status_code=201)
async def create_organization(
    payload: CreateOrgRequest,
    db: AsyncSession = Depends(get_public_db)
):
    """
    Create new organization
    User must be authenticated (has access token)
    """
    token_data = get_current_user_access_token()
    user_id = token_data.get("sub")
    
    org_service = OrganizationService(db)
    
    try:
        org = await org_service.create_organization(
            name=payload.name,
            owner_id=user_id,
            description=payload.description,
            slug=payload.slug
        )
        
        return send_custom_response(
            {
                "id": str(org.id),
                "name": org.name,
                "slug": org.slug,
                "description": org.description,
                "owner_id": str(org.owner_id),
                "status": org.status
            },
            success_message="Organization created successfully",
            status_code=201
        )
    except HttpError:
        raise
    except Exception as e:
        raise HttpError(500, "Failed to create organization", str(e))


@router.get("/my-organizations")
async def get_my_organizations(
    db: AsyncSession = Depends(get_public_db)
):
    """Get all organizations current user belongs to"""
    token_data = get_current_user_access_token()
    user_id = token_data.get("sub")
    
    org_service = OrganizationService(db)
    orgs = await org_service.get_user_organizations(user_id)
    
    return send_custom_response(orgs)


@router.post("/switch/{org_id}")
async def switch_organization(
    org_id: str,
    db: AsyncSession = Depends(get_public_db)
):
    """
    Switch to a different organization
    Returns new tokens with orgId embedded
    """
    token_data = get_current_user_access_token()
    user_id = token_data.get("sub")
    email = token_data.get("email")
    
    org_service = OrganizationService(db)
    
    # Verify user is member of this org
    is_member = await org_service.is_user_in_org(user_id, org_id)
    if not is_member:
        raise HttpError(403, "You are not a member of this organization", "NOT_ORG_MEMBER")
    
    # Get org details
    org = await org_service.get_organization(org_id)
    
    # Create new tokens with orgId
    new_access_token = create_access_token(
        {"sub": user_id, "email": email},
        org_id=org_id
    )
    new_refresh_token = create_refresh_token(user_id, org_id=org_id)
    
    return send_custom_response(
        {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "organization": {
                "id": str(org.id),
                "name": org.name,
                "slug": org.slug,
                "description": org.description,
                "owner_id": str(org.owner_id),
                "status": org.status
            }
        },
        success_message="Switched organization successfully"
    )


@router.get("/{org_id}")
async def get_organization(
    org_id: str,
    db: AsyncSession = Depends(get_public_db)
):
    """Get organization details"""
    org_service = OrganizationService(db)
    org = await org_service.get_organization(org_id)
    
    return send_custom_response({
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "description": org.description,
        "owner_id": str(org.owner_id),
        "status": org.status
    })
