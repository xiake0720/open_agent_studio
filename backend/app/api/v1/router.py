from fastapi import APIRouter

from backend.app.api.v1 import admin, agent_runs, auth, chat, conversations, generated_images, health, messages, models

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(conversations.router)
api_router.include_router(messages.router)
api_router.include_router(models.router)
api_router.include_router(chat.router)
api_router.include_router(agent_runs.router)
api_router.include_router(generated_images.router)
api_router.include_router(admin.router)
