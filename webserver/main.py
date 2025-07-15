from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime
import json
import os
from typing import Optional
from enum import Enum

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# User roles enum
class UserRole(str, Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"

# Simple data storage (나중에 데이터베이스로 교체 가능)
DIARY_FILE = "public_diary_board.json"
USERS_FILE = "users.json"

def load_diary_entries():
    """공개 일기 게시판 데이터 로드"""
    if os.path.exists(DIARY_FILE):
        with open(DIARY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_diary_entry(title, content, emotion, author, date):
    """공개 일기 게시판에 데이터 저장"""
    entries = load_diary_entries()
    new_entry = {
        "id": len(entries) + 1,
        "title": title,
        "content": content,
        "emotion": emotion,
        "author": author,
        "date": date,
        "created_at": datetime.now().isoformat()
    }
    entries.append(new_entry)
    
    with open(DIARY_FILE, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    
    return new_entry

def get_emotion_stats():
    """감정 통계 데이터 생성"""
    entries = load_diary_entries()
    emotion_counts = {}
    total_entries = len(entries)
    
    for entry in entries:
        emotion = entry.get('emotion', '😊')
        emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
    
    # 감정별 점수 계산 (예시)
    emotion_scores = {
        '😊': 5,  # 기쁨
        '😌': 4,  # 평온
        '😟': 2,  # 걱정
        '😢': 1,  # 슬픔
        '😠': 1   # 화남
    }
    
    total_score = sum(emotion_scores.get(emotion, 3) * count for emotion, count in emotion_counts.items())
    average_score = total_score / total_entries if total_entries > 0 else 0
    
    return {
        "emotion_counts": emotion_counts,
        "total_entries": total_entries,
        "average_score": round(average_score, 2),
        "total_score": total_score
    }

def get_current_user_role() -> UserRole:
    """현재 사용자의 역할 반환 (임시로 customer 반환, 나중에 세션/JWT 기반으로 변경)"""
    # TODO: 실제 사용자 인증 시스템 구현 후 수정
    return UserRole.CUSTOMER

# ==================== 페이지 라우트들 ====================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """홈 페이지 - 대시보드 형태"""
    today = datetime.now().strftime("%Y년 %m월 %d일")
    stats = get_emotion_stats()
    current_role = get_current_user_role()
    
    return templates.TemplateResponse("home.html", {
        "request": request,
        "today": today,
        "stats": stats,
        "current_role": current_role
    })

@app.get("/write", response_class=HTMLResponse)
async def write_diary_page(request: Request):
    """일기 작성 페이지"""
    today = datetime.now().strftime("%Y년 %m월 %d일")
    current_role = get_current_user_role()
    
    return templates.TemplateResponse("write.html", {
        "request": request,
        "today": today,
        "current_role": current_role
    })

@app.get("/view", response_class=HTMLResponse)
async def view_diary_page(request: Request):
    """일기 보기 페이지 (게시판)"""
    today = datetime.now().strftime("%Y년 %m월 %d일")
    all_entries = load_diary_entries()
    all_entries.reverse()  # 최신순
    current_role = get_current_user_role()
    
    return templates.TemplateResponse("view.html", {
        "request": request,
        "today": today,
        "all_entries": all_entries,
        "total_entries": len(all_entries),
        "current_role": current_role
    })

# @app.get("/stats", response_class=HTMLResponse)
# async def emotion_stats_page(request: Request):
#     """감정 통계/스코어 페이지"""
#     today = datetime.now().strftime("%Y년 %m월 %d일")
#     stats = get_emotion_stats()
#     current_role = get_current_user_role()
    
#     return templates.TemplateResponse("stats.html", {
#         "request": request,
#         "today": today,
#         "stats": stats,
#         "current_role": current_role
#     })

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """설정 페이지 (고객용/관리자용 구분)"""
    today = datetime.now().strftime("%Y년 %m월 %d일")
    current_role = get_current_user_role()
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "today": today,
        "current_role": current_role
    })

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """관리자 전용 페이지"""
    current_role = get_current_user_role()
    
    # 관리자가 아니면 접근 거부
    if current_role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="관리자만 접근 가능합니다.")
    
    today = datetime.now().strftime("%Y년 %m월 %d일")
    all_entries = load_diary_entries()
    stats = get_emotion_stats()
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "today": today,
        "all_entries": all_entries,
        "stats": stats,
        "current_role": current_role
    })

# ==================== API 엔드포인트들 ====================

@app.post("/save-diary")
async def save_diary(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    author: str = Form(...),
    emotion: str = Form(default="😊")
):
    """일기 저장 API"""
    today = datetime.now().strftime("%Y.%m.%d")
    new_entry = save_diary_entry(title, content, emotion, author, today)
    return RedirectResponse(url="/view", status_code=303)

@app.get("/api/diary-entries")
async def get_diary_entries():
    """공개 일기 게시판 API (JSON)"""
    entries = load_diary_entries()
    return {"entries": entries, "total": len(entries)}

# @app.get("/api/stats")
# async def get_stats():
#     """감정 통계 API (JSON)"""
#     return get_emotion_stats() 