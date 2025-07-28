from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel
import logging

# DB관련
from pymongo import MongoClient
import bcrypt
from jose import jwt

import pprint
import json
import os
import datetime
from typing import Optional, List
from enum import Enum
import secrets

import requests # 추가
import httpx # 추가
from dotenv import load_dotenv # 추가

# .env 파일에서 환경 변수 로드
load_dotenv()
SOLAR_API_KEY = os.getenv("API_KEY")
SOLAR_API_URL = "https://api.upstage.ai/v1/solar/chat/completions"

# --- 디버깅 코드 추가 ---
if SOLAR_API_KEY:
    print(f"✅ API 키가 성공적으로 로드되었습니다. (길이: {len(SOLAR_API_KEY)}, 시작: {SOLAR_API_KEY[:4]}...)" )
else:
    print("⚠️ API 키를 로드하지 못했습니다. .env 파일을 확인해주세요.")
# --- 디버깅 코드 끝 ---


# ==================== 전역 변수 및 설정 ====================

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# User roles enum
class UserRole(str, Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"

# 데이터베이스 연결
client = MongoClient('mongodb://localhost:27017/')
db = client.emotlink_db
users = db.users
diaries = db.diaries

# 채팅 대화 임시 저장소
chat_sessions = {}

# ----------------- AI_QUESTIONS 리스트 제거 -----------------
# AI가 직접 질문을 생성하므로, 기존의 고정 질문 리스트는 제거합니다.
# AI_QUESTIONS = [ ... ]


# ==================== Pydantic 모델 ====================

class Diary(BaseModel):
    title: str
    content: str
    emotion: str
    author: str

class ChatMessage(BaseModel):
    message: str

# SECRET_KEY for jwt
secret_file = []
with open("./webserver/config/secret_key.json", "r") as f:
    secret_file = json.load(f)
SECRET_KEY = secret_file["SECRET_KEY"]

DATETIME_STR_FORMAT = "%Y.%m.%d %H:%M" # ex) "2025.07.01 00:08"

# 로거 설정 (터미널에 에러를 기록)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)






# ====================== server logics ==========================

def create_login_token(data, expire = 120):
    user = data.copy()
    user.update({"expire" : int((datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=expire)).timestamp())})
    return jwt.encode(user, SECRET_KEY, "HS256")

def load_diary_entries(request, max_limit = 0) -> list:
    """load user diaries"""
    user_id = get_current_user(request)["id"]
    user_diaries: list = list(diaries.find({"author_id" : user_id}, limit = max_limit))
    if user_diaries is None:
        user_diaries = []
    return user_diaries
    

def save_diary_entry(title, content, emotion, author, date):
    """save new diary in db"""
    new_entry = {
        "title": title,
        "content": content,
        "emotion": emotion,
        "author_id": author,
        "created_at": date,
        "last_modified" : datetime.datetime.now(datetime.timezone.utc)
    }
    diaries.insert_one(new_entry)
    return new_entry

def get_emotion_stats(request: Request):
    """감정 통계 데이터 생성"""
    entries = load_diary_entries(request)
    emotion_counts = {}
    total_entries = len(list(entries))
        
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

# ==================== 유틸리티 함수 ====================

async def get_ai_question(conversation_history: List[dict]) -> dict:
    """Solar API를 호출하여 다음 질문 또는 최종 메시지를 생성합니다."""
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SOLAR_API_KEY}"
    }

    user_message_count = len([msg for msg in conversation_history if msg["role"] == "user"])

    if user_message_count < 5:
        system_prompt = (
            "당신은 사용자가 하루를 되돌아보며 일기를 쓸 수 있도록 돕는 친절하고 공감 능력 높은 AI 상담가입니다. "
            "주어진 이전 대화 내용을 바탕으로, 사용자의 말에 먼저 자연스럽게 공감하며 짧은 맞장구를 쳐주세요. "
            "그 다음에, 대화의 흐름에 맞춰 감정과 경험을 더 깊이 탐색할 수 있는 후속 질문을 하나만 던져주세요. "
            "모든 답변은 부드럽고 자연스러운 한국어 대화체로 해주세요. 질문만 툭 던지는 느낌을 주면 안 됩니다."
        )
    else:
        system_prompt = (
            "지금까지의 대화 내용을 종합해서 따뜻하고 격려하는 어조로 마무리 인사를 해주세요. "
            "그리고 대화가 모두 끝났음을 명확히 알려주세요. "
            "반드시 메시지 끝에 'END_CHAT'이라는 키워드를 포함해야 합니다."
        )

    # 대화 기록을 단일 문자열로 변환
    history_string = "\n".join([f"{'상담가' if msg['role'] == 'assistant' else '사용자'}: {msg['content']}" for msg in conversation_history])
    
    # API에 전달할 사용자 메시지 구성
    user_prompt = f"""
이전 대화 내용:
---
{history_string}
---
위 대화에 이어, 시스템 프롬프트의 지시에 따라 다음 응답을 생성해주세요.
"""

    # API에 보낼 메시지 형식 수정
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    payload = {
        "model": "solar-1-mini-chat",
        "messages": messages,
        "temperature": 0.5,
        "top_p": 0.9, # 파라미터 추가
        "n": 1, # 파라미터 추가
        "stream": False
    }

    try:
        # requests.post를 httpx.AsyncClient.post로 변경
        async with httpx.AsyncClient() as client:
            response = await client.post(SOLAR_API_URL, headers=headers, json=payload, timeout=30.0)
            response.raise_for_status() # 오류 발생 시 예외 처리
        
        ai_response = response.json()["choices"][0]["message"]["content"]
        
        if "END_CHAT" in ai_response:
            return {"response": ai_response.replace("END_CHAT", "").strip(), "finished": True}
        else:
            return {"response": ai_response, "finished": False}

    except httpx.RequestError as e:
        print(f"Solar API 호출 오류: {e}")
        return {"response": "죄송합니다, AI 모델과 통신하는 중 오류가 발생했어요. 잠시 후 다시 시도해주세요.", "finished": True}


async def generate_and_save_diary(user_id: str, conversation_history: List[dict]):
    """Solar API를 호출하여 대화 내용 기반으로 일기를 생성하고 저장합니다."""
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SOLAR_API_KEY}"
    }

    system_prompt = (
        "당신은 주어진 대화 내용을 바탕으로 감정이 담긴 일기를 작성하는 작가입니다. "
        "대화의 핵심 내용을 요약하여, 사용자의 경험과 감정이 잘 드러나는 자연스러운 일기 형식의 글을 작성해주세요. "
        "응답은 반드시 다음 형식에 맞춰주세요. 각 항목은 줄바꿈으로 구분합니다.\n"
        "제목: [여기에 20자 내외의 일기 제목 작성]\n"
        "내용:\n"
        "[여기에 3~4문단으로 구성된 일기 본문 작성]\n"
        "감정: [기쁨, 평온, 걱정, 슬픔, 화남 중 가장 적절한 감정 하나만 텍스트로 작성]"
    )
    
    history_string = "\n".join([f"{'상담가' if msg['role'] == 'assistant' else '사용자'}: {msg['content']}" for msg in conversation_history])

    user_prompt = f"""
다음은 사용자와 상담가 간의 대화 내용입니다.
---
{history_string}
---
위 대화 내용을 바탕으로, 시스템 프롬프트의 지시에 따라 일기를 생성해주세요.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    payload = {
        "model": "solar-1-mini-chat",
        "messages": messages,
        "temperature": 0.7,
        "stream": False
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(SOLAR_API_URL, headers=headers, json=payload, timeout=60.0)
            response.raise_for_status()
        
        diary_text = response.json()["choices"][0]["message"]["content"]
        
        # 생성된 텍스트에서 제목, 내용, 감정 파싱
        lines = diary_text.strip().split('\n')
        
        parsed_data = {}
        is_content_section = False

        for line in lines:
            line_stripped = line.strip()
            if line_stripped.startswith("제목:"):
                parsed_data['title'] = line_stripped.replace("제목:", "").strip()
                is_content_section = False
            elif line_stripped.startswith("내용:"):
                is_content_section = True
                parsed_data['content'] = []
            elif line_stripped.startswith("감정:"):
                parsed_data['emotion'] = line_stripped.replace("감정:", "").strip()
                is_content_section = False
            elif is_content_section:
                parsed_data['content'].append(line)

        title = parsed_data.get('title', "자동 생성된 일기")
        content = "\n".join(parsed_data.get('content', ["내용을 생성하지 못했습니다."])).strip()
        emotion_text = parsed_data.get('emotion', "기쁨")

        emotion_map = {'기쁨': '😊', '평온': '😌', '걱정': '😟', '슬픔': '😢', '화남': '😠'}
        emotion = emotion_map.get(emotion_text, "😊")
        
        save_diary_entry(title, content, emotion, user_id, datetime.datetime.now(datetime.timezone.utc))
        print(f"✅ Diary automatically saved for user {user_id}")

    except Exception as e:
        print(f"❌ 일기 생성 또는 저장 중 오류 발생: {e}")
        fallback_content = "대화를 바탕으로 일기를 생성하는 데 실패했습니다.\n\n" + history_string
        save_diary_entry("일기 생성 실패", fallback_content, "😟", user_id, datetime.datetime.now(datetime.timezone.utc))


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
    if len(password) < 8:
        return templates.TemplateResponse("signup.html", {"request": request, "error": "비밀번호는 8자 이상이어야 합니다."})
    
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
    stats = get_emotion_stats(request)
    
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

    all_entries = load_diary_entries(request)
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
        
    stats = get_emotion_stats(request)
    
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
    
    all_entries = load_diary_entries(request)
    stats = get_emotion_stats(request)
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "all_entries": all_entries,
        "stats": stats,
        "current_user": current_user, # 사용자 정보 전달
    })
    
# ================== 예외 핸들러 =======================
    
@app.exception_handler(404)
async def not_found_exception_handler(request: Request, exc: HTTPException):
    # return 404.html when 404 not found
    return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # 500 internal server error, etc
    logger.error(f"An unexpected error occurred: {exc}", exc_info=True)
    return templates.TemplateResponse("500.html", {"request": request}, status_code=500)

# ==================== API 엔드포인트들 ====================

@app.post("/chat/start")
async def start_chat(request: Request):
    """채팅 세션을 초기화하고 고정된 첫 질문을 반환합니다."""
    current_user = get_current_user(request)
    if not current_user:
        return JSONResponse(status_code=401, content={"error": "Authentication required"})

    user_id = current_user.get("id")
    
    # 안정적인 대화 시작을 위해 첫 질문은 고정된 값으로 사용
    first_question = "안녕하세요! 오늘 하루는 어떠셨나요?"
    
    # 대화 기록 초기화 및 첫 메시지 저장 (role: 'assistant'로 변경)
    chat_sessions[user_id] = [{"role": "assistant", "content": first_question}]
    
    return JSONResponse(content={"response": first_question, "finished": False})

@app.post("/chat/message")
async def post_chat_message(request: Request, user_message: ChatMessage):
    """사용자 메시지를 처리하고 다음 AI 응답을 반환합니다."""
    current_user = get_current_user(request)
    if not current_user:
        return JSONResponse(status_code=401, content={"error": "Authentication required"})
    
    user_id = current_user.get("id")

    if user_id not in chat_sessions:
        return JSONResponse(status_code=400, content={"error": "채팅 세션이 시작되지 않았습니다."})

    # 현재 대화 기록에 사용자 메시지 추가
    current_conversation = chat_sessions[user_id]
    current_conversation.append({"role": "user", "content": user_message.message})
    
    # AI에게 다음 질문 생성 요청 (await 추가)
    ai_message = await get_ai_question(current_conversation)
    
    # AI 응답을 대화 기록에 추가 (role: 'assistant'로 변경)
    current_conversation.append({"role": "assistant", "content": ai_message["response"]})

    # 대화 종료 시 일기 자동 생성 및 세션 정리
    if ai_message.get("finished"):
        # 백그라운드에서 일기 생성 및 저장 실행 (응답이 사용자에게 즉시 가도록)
        await generate_and_save_diary(user_id, current_conversation)
        if user_id in chat_sessions:
            del chat_sessions[user_id]
        
    return JSONResponse(content=ai_message)


@app.post("/save-diary")
async def save_diary(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    author: str = Form(...),
    emotion: str = Form(default="😊")
):
    """일기 저장 API"""
    today: datetime  = datetime.datetime.now(datetime.timezone.utc)
    current_user: dict | None = get_current_user(request)
    new_entry = save_diary_entry(title, content, emotion, current_user.get("id"), today)
    
    return RedirectResponse(url="/view", status_code=303)

@app.get("/api/diary-entries")
async def get_diary_entries(request: Request):
    """공개 일기 게시판 API (JSON)"""
    entries = load_diary_entries(request)
    return {"entries": entries, "total": len(list(entries))}

@app.get("/api/stats")
async def get_stats(request: Request):
    """감정 통계 API (JSON)"""
    return get_emotion_stats(request)