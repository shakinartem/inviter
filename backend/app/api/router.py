from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.core.security import auth_backend, fastapi_users
from app.features.accounts.api import router as accounts_router
from app.features.auth.schemas import UserCreate, UserRead, UserUpdate
from app.features.connectors.api import router as connectors_router
from app.features.parser.api import router as parser_router
from app.features.proxies.api import router as proxies_router
from app.features.inviter.api import router as inviter_router

api_router = APIRouter()
api_router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
api_router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
api_router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(accounts_router, tags=["accounts"])
api_router.include_router(connectors_router, tags=["connectors"])
api_router.include_router(proxies_router, tags=["proxies"])
api_router.include_router(inviter_router, tags=["inviter"])
api_router.include_router(parser_router, tags=["parser"])
