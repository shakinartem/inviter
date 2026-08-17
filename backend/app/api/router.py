from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.core.config import settings
from app.core.security import auth_backend, fastapi_users
from app.features.accounts.api import router as accounts_router
from app.features.allocations.api import router as allocations_router
from app.features.allocations.frontier_api import router as allocation_frontier_router
from app.features.auth.schemas import UserCreate, UserRead, UserUpdate
from app.features.connections.api import router as connections_router
from app.features.connectors.api import router as connectors_router
from app.features.discovery.api import router as discovery_router
from app.features.experiments.api import router as experiments_router
from app.features.experiments.analysis_api import router as experiment_analysis_router
from app.features.experiments.contextual_api import router as experiment_contextual_router
from app.features.experiments.contextual_value_api import router as experiment_contextual_value_router
from app.features.experiments.evidence_health_api import router as experiment_evidence_health_router
from app.features.experiments.meta_api import router as experiment_meta_router
from app.features.experiments.power_api import router as experiment_power_router
from app.features.experiments.value_api import router as experiment_value_router
from app.features.intelligence.api import router as intelligence_router
from app.features.intelligence.intent_api import router as intent_router
from app.features.learning.api import router as learning_router
from app.features.learning.webhook_api import router as outcome_webhook_router
from app.features.orchestration.api import router as orchestration_router
from app.features.orchestration.campaign_api import router as campaign_create_router
from app.features.parser.api import router as parser_router
from app.features.proxies.api import router as proxies_router
from app.features.inviter.api import router as inviter_router
from app.features.segments.causal_portfolio_api import router as segment_causal_portfolio_router
from app.features.segments.preview_api import router as segment_preview_router
from app.features.segments.portfolio_api import router as segment_portfolio_router
from app.features.segments.forecast_api import router as segment_forecast_router
from app.features.segments.api import router as segments_router

api_router = APIRouter()
api_router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
if settings.allow_registration:
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
api_router.include_router(connections_router, tags=["connections"])
api_router.include_router(connectors_router, tags=["connectors"])
api_router.include_router(discovery_router, tags=["discovery"])

# Static experiment workspaces must be registered before dynamic experiment routes.
api_router.include_router(experiment_evidence_health_router, tags=["experiments", "evidence-health"])
api_router.include_router(experiment_contextual_value_router, tags=["experiments", "contextual-value"])
api_router.include_router(experiment_contextual_router, tags=["experiments", "contextual-yield"])
api_router.include_router(experiment_value_router, tags=["experiments", "incremental-value"])
api_router.include_router(experiment_meta_router, tags=["experiments", "incremental-yield"])
api_router.include_router(experiment_power_router, tags=["experiments", "power-planning"])
api_router.include_router(experiment_analysis_router, tags=["experiments", "causal-analysis"])
api_router.include_router(experiments_router, tags=["experiments"])

api_router.include_router(intelligence_router, tags=["intelligence"])
api_router.include_router(intent_router, tags=["intent"])

# Static Opportunity analytics must precede the dynamic segment router.
api_router.include_router(segment_preview_router, tags=["segments"])
api_router.include_router(segment_causal_portfolio_router, tags=["segments", "causal-portfolio"])
api_router.include_router(segment_portfolio_router, tags=["segments", "forecast", "portfolio"])
api_router.include_router(segment_forecast_router, tags=["segments", "forecast"])
api_router.include_router(segments_router, tags=["segments"])

api_router.include_router(allocation_frontier_router, tags=["allocations", "capacity-economics"])
api_router.include_router(allocations_router, tags=["allocations"])
api_router.include_router(learning_router, tags=["learning"])
api_router.include_router(outcome_webhook_router, tags=["learning", "outcome-webhooks"])
api_router.include_router(campaign_create_router, tags=["orchestration"])
api_router.include_router(orchestration_router, tags=["orchestration"])
api_router.include_router(proxies_router, tags=["proxies"])
api_router.include_router(inviter_router, tags=["inviter"])
api_router.include_router(parser_router, tags=["parser"])
