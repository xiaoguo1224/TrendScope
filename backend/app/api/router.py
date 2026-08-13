from fastapi import APIRouter

from app.api import configuration, research_tasks

api_router = APIRouter()
api_router.include_router(research_tasks.router)
api_router.include_router(configuration.router)
