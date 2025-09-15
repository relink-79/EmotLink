from .chat import *
from . import chat, diary, stats, linker
from fastapi import APIRouter

emoter_router = APIRouter()
emoter_router.include_router(chat.router)
emoter_router.include_router(diary.router)
emoter_router.include_router(stats.router)
emoter_router.include_router(linker.router)