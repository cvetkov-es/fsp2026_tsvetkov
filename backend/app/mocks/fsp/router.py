from fastapi import APIRouter

from app.mocks.fsp import api, oidc

router = APIRouter()
router.include_router(oidc.router)
router.include_router(api.router)
