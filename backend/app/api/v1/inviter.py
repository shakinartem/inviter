from app.features.inviter.api import router as inviter_router

# The inviter_router already has prefix="/campaigns", so when included in the v1 router,
# the full path will be /api/v1/campaigns