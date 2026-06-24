from fastapi import APIRouter

from backend.app.api.v1 import health,conversations

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(conversations.router)