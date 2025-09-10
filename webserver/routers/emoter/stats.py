from fastapi import Request, APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse
from .diary import get_emotion_stats
from ..auth.auth import get_current_user
from ...shared import templates

router = APIRouter()

@router.get("/stats", response_class=HTMLResponse)
async def emotion_stats_page(request: Request):
    """감정 통계/스코어 페이지"""
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
        
    stats = get_emotion_stats(request)
    
    return templates.TemplateResponse("stats.html", {
        "request": request,
        "stats": stats,
        "current_user": current_user, # 사용자 정보 전달
    })
    

@router.get("/api/stats")
async def get_stats(request: Request):
    """감정 통계 API (JSON)"""
    return get_emotion_stats(request)