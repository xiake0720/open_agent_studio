from fastapi import APIRouter

from backend.app.api.v1 import health,conversations,messages,models,chat

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(conversations.router)
api_router.include_router(messages.router)
api_router.include_router(models.router)
api_router.include_router(chat.router)