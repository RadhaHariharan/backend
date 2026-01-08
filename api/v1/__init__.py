from fastapi import APIRouter
from api.v1.routes.auth import router as auth_router

router = APIRouter()
router.include_router(auth_router)
