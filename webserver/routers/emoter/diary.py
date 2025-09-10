from fastapi import Request
from ...shared import *
from ...config import *
import datetime
from fastapi import Request, APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Form

from ..auth.auth import get_current_user


def load_diary_entries(request, max_limit = 0) -> list:
    """load user diaries"""
    current_user = get_current_user(request)
    if current_user is None:
        return []
    user_id = current_user["id"]
    user_diaries: list = list(diaries.find({"author_id" : user_id}, limit = max_limit))
    if user_diaries is None:
        user_diaries = []
    return user_diaries
    

def save_diary_entry(title, content, emotion, author, date, depression=0, isolation=0, frustration=0):
    """save new diary in db"""
    new_entry = {
        "title": title,
        "content": content,
        "emotion": emotion,
        "author_id": author,
        "created_at": date,
        "last_modified" : datetime.datetime.now(datetime.timezone.utc),
        "depression": depression,
        "isolation": isolation,
        "frustration": frustration
    }
    diaries.insert_one(new_entry)
    return new_entry

def get_emotion_stats(request: Request):
    """감정 통계 데이터 생성"""
    diary_entries = list(load_diary_entries(request))
    total_entries = len(diary_entries)
    
    if total_entries == 0:
        return {
            "emotion_counts": {},
            "total_entries": 0,
            "average_score": 0,
            "total_score": 0,
            "avg_depression": 0,
            "avg_isolation": 0,
            "avg_frustration": 0,
        }

    emotion_counts = {}
    total_depression = 0
    total_isolation = 0
    total_frustration = 0

    for entry in diary_entries:
        emotion = entry.get('emotion', '😊')
        emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
        
        total_depression += entry.get('depression', 0)
        total_isolation += entry.get('isolation', 0)
        total_frustration += entry.get('frustration', 0)

    # 기존 감정 스코어 계산 (예시)
    emotion_scores = {
        '😊': 5, '😄': 5, '😌': 4, '🙏': 4, 
        '😟': 2, '😰': 2, 
        '😢': 1, '😠': 1, '😔': 1
    }
    
    total_score = sum(emotion_scores.get(emotion, 3) * count for emotion, count in emotion_counts.items())
    average_score = total_score / total_entries

    return {
        "emotion_counts": emotion_counts,
        "total_entries": total_entries,
        "average_score": round(average_score, 2),
        "total_score": total_score,
        "avg_depression": round(total_depression / total_entries, 1),
        "avg_isolation": round(total_isolation / total_entries, 1),
        "avg_frustration": round(total_frustration / total_entries, 1),
    }
    
    
    
    
    
    
# ============= router =============

router = APIRouter()

@router.get("/write", response_class=HTMLResponse)
async def write_diary_page(request: Request):
    """일기 작성 페이지"""
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
        
    return templates.TemplateResponse("write.html", {
        "request": request,
        "current_user": current_user, # 사용자 정보 전달
    })

@router.get("/view", response_class=HTMLResponse)
async def view_diary_page(request: Request):
    """일기 보기 페이지 (게시판)"""
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    all_entries = load_diary_entries(request)
    all_entries.reverse()  # 최신순
    
    return templates.TemplateResponse("view.html", {
        "request": request,
        "all_entries": all_entries,
        "total_entries": len(all_entries),
        "current_user": current_user, # 사용자 정보 전달
    })

@router.post("/save-diary")
async def save_diary(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    author: str = Form(...),
    emotion: str = Form(default="😊")
):
    """일기 저장 API"""
    today = datetime.datetime.now(datetime.timezone.utc)
    current_user = get_current_user(request)
    if current_user:
        save_diary_entry(title, content, emotion, current_user.get("id"), today)
    
    return RedirectResponse(url="/view", status_code=303)

@router.get("/api/diary-entries")
async def get_diary_entries(request: Request):
    """공개 일기 게시판 API (JSON)"""
    entries = load_diary_entries(request)
    return {"entries": entries, "total": len(list(entries))}