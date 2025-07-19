from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

# DB관련
from pymongo import MongoClient
import bcrypt
from jose import jwt

import pprint
import json
import os
import datetime
from typing import Optional
from enum import Enum
import secrets

app = FastAPI()

# 세션 미들웨어 추가
app.add_middleware(SessionMiddleware, secret_key="your-secret-key-change-in-production")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# User roles enum
class UserRole(str, Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"

# Simple data storage (나중에 데이터베이스로 교체 가능)
client = MongoClient(host='localhost', port=27017)
db = client["emotelink"]
users = db["users"]

test_user = {
    "id" : "goranipie",
    "password" : bcrypt.hashpw("0000".encode('utf-8'), bcrypt.gensalt()).decode("utf-8"),
    "birthday" : datetime.datetime.utcnow(),
    "name" : "김춘자",
    "account_type" : 0,
}
print(users.insert_one(test_user).inserted_id)

DIARY_FILE = "public_diary_board.json"
USERS_FILE = "users.json"

secret_file = []
with open("./webserver/config/secret_key.json", "r") as f:
    secret_file = json.load(f)
SECRET_KEY = secret_file["SECRET_KEY"]

def create_login_token(data, expire = 120):
    user = data.copy()
    user.update({"expire" : int((datetime.datetime.now() + datetime.timedelta(hours=expire)).strftime("%Y%m%d"))})
    return jwt.encode(user, SECRET_KEY, "HS256")

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

def get_current_user(request: Request) -> Optional[dict]:
    """JWT 토큰에서 현재 사용자 정보(dict)를 반환합니다."""
    try:
        token = request.cookies.get("login_token")
        if token:
            return jwt.decode(token, SECRET_KEY, "HS256")
    except Exception:
        pass
    return None

def get_current_user_role(request: Request) -> Optional[str]:
    """현재 사용자의 역할 반환 (JWT 토큰 기반)"""
    user = get_current_user(request)
    if user:
        return user.get("role")
    return None

# ==================== 로그인/로그아웃 라우트 ====================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """로그인 페이지를 표시합니다."""
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, id: str = Form(...), password: str = Form(...), remember: Optional[bool] = Form(None), dev_mode: Optional[bool] = Form(None)):
    """사용자 로그인을 처리합니다."""
    print("로그인 시도 감지")
    current_user = users.find_one({"id" : id}) # 유저 없을시 None반환

    # 일반 로그인 (test/test)
    if (id != None) and \
    (password != None) and \
    (current_user != None) and \
    (bcrypt.checkpw(password.encode("utf-8"), current_user["password"].encode("utf-8"))):
        
        # 토큰에 포함할 사용자 정보 생성
        user_info_for_token = {
            "id": current_user.get("id"),
            "name": current_user.get("name"),
            "role": "customer"  # 역할은 직접 지정
        }
        
        # 새 토큰 생성
        login_token = create_login_token(user_info_for_token)
        
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            key="login_token",
            value=login_token,
            httponly=True,
            samesite="lax",
        )
        return response

    # 로그인 실패
    print("아이디 비번 불일치")
    return templates.TemplateResponse("login.html", {"request": request, "error": "잘못된 사용자 이름 또는 비밀번호입니다."})
    # return RedirectResponse(url="/login", status_code=303)

@app.get("/logout")
async def logout(request: Request):
    """사용자 세션을 지워 로그아웃합니다."""
    response = RedirectResponse(url="/login")
    response.delete_cookie("login_token")
    return response

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    """회원가입 페이지를 표시합니다."""
    return templates.TemplateResponse("signup.html", {"request": request})

@app.post("/signup")
async def signup(request: Request, 
                id: str = Form(...), 
                name: str = Form(...), 
                password: str = Form(...), 
                password_confirm: str = Form(...), 
                birthday: str = Form(...)):
    """회원가입 정보를 받아 DB에 저장합니다."""
    
    # 1. 유효성 검사
    if password != password_confirm:
        return templates.TemplateResponse("signup.html", {"request": request, "error": "비밀번호가 일치하지 않습니다."})
    if len(password) < 4:
        return templates.TemplateResponse("signup.html", {"request": request, "error": "비밀번호는 4자 이상이어야 합니다."})
    
    # 2. 아이디 중복 확인
    if users.find_one({"id": id}):
        return templates.TemplateResponse("signup.html", {"request": request, "error": "이미 사용 중인 아이디입니다."})

    # 3. 스키마에 맞게 데이터 가공
    try:
        new_user = {
            "id": id,
            "name": name,
            "password": bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode("utf-8"),
            "birthday": datetime.datetime.strptime(birthday, "%Y-%m-%d"),
            "account_type": 0,
        }
    except Exception as e:
        # 데이터 가공 중 오류 발생 시, 사용자에게 에러를 알림 (터미널에는 로그를 남기는 것이 좋음)
        print(f"Data processing error during signup: {e}")
        return templates.TemplateResponse("signup.html", {"request": request, "error": "입력된 정보가 올바르지 않습니다."})

    # 4. 데이터베이스에 저장
    try:
        users.insert_one(new_user)
    except Exception as e:
        # DB 저장 중 심각한 오류 발생 시, 사용자에게 에러를 알림 (터미널에는 로그를 남기는 것이 좋음)
        print(f"DB insertion error during signup: {e}")
        return templates.TemplateResponse("signup.html", {"request": request, "error": "회원가입 중 서버 오류가 발생했습니다."})

    # 5. 성공 응답
    return templates.TemplateResponse("signup.html", {
        "request": request, 
        "success": "회원가입이 완료되었습니다! 로그인 페이지로 이동하여 로그인해 주세요."
    })

# ==================== 페이지 라우트들 ====================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    
    current_user = get_current_user(request)
    if not current_user: # 로그인 안됐을 때
        return RedirectResponse(url="/login", status_code=303)
    
    # 로그인 됐을 때
    stats = get_emotion_stats()
    
    return templates.TemplateResponse("home.html", {
        "request": request,
        "stats": stats,
        "current_user": current_user, # 사용자 정보 전달
    })

@app.get("/write", response_class=HTMLResponse)
async def write_diary_page(request: Request):
    """일기 작성 페이지"""
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
        
    return templates.TemplateResponse("write.html", {
        "request": request,
        "current_user": current_user, # 사용자 정보 전달
    })

@app.get("/view", response_class=HTMLResponse)
async def view_diary_page(request: Request):
    """일기 보기 페이지 (게시판)"""
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    all_entries = load_diary_entries()
    all_entries.reverse()  # 최신순
    
    return templates.TemplateResponse("view.html", {
        "request": request,
        "all_entries": all_entries,
        "total_entries": len(all_entries),
        "current_user": current_user, # 사용자 정보 전달
    })

@app.get("/stats", response_class=HTMLResponse)
async def emotion_stats_page(request: Request):
    """감정 통계/스코어 페이지"""
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
        
    stats = get_emotion_stats()
    
    return templates.TemplateResponse("stats.html", {
        "request": request,
        "stats": stats,
        "current_user": current_user, # 사용자 정보 전달
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """설정 페이지 (고객용/관리자용 구분)"""
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
        
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "current_user": current_user, # 사용자 정보 전달
    })

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """관리자 전용 페이지"""
    current_user = get_current_user(request)
    # 관리자가 아니거나 로그인하지 않았으면 접근 거부
    if not current_user or current_user.get("role") != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="관리자만 접근 가능합니다.")
    
    all_entries = load_diary_entries()
    stats = get_emotion_stats()
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "all_entries": all_entries,
        "stats": stats,
        "current_user": current_user, # 사용자 정보 전달
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

@app.get("/api/stats")
async def get_stats():
    """감정 통계 API (JSON)"""
    return get_emotion_stats() 