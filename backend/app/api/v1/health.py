from fastapi import APIRouter

router = APIRouter()


@router.get("/", summary="API health check")
async def api_healthcheck() -> dict[str, str]:
    return {"status": "ok", "scope": "api"}
