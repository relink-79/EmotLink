from fastapi import FastAPI, Request, Form, Depends, HTTPException, UploadFile
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
import redis
import uuid_utils

import pprint
import json
import os
import sys
import datetime
import time
from typing import Optional, List
from enum import Enum
import secrets
import base64

import requests # 추가
import httpx # 추가
from dotenv import load_dotenv # 추가

# 서버 로직 분리 모듈
from .web_middleware import *




# .env 파일에서 환경 변수 로드
load_dotenv()
SOLAR_API_KEY = os.getenv("API_KEY")
TTS_KEY = os.getenv("TTS_KEY") # Google STT 키 로드
SOLAR_API_URL = "https://api.upstage.ai/v1/solar/chat/completions"
GOOGLE_STT_URL = "https://speech.googleapis.com/v1/speech:recognize"

# --- 디버깅 코드 추가 ---
if SOLAR_API_KEY:
    print(f"✅ API 키가 성공적으로 로드되었습니다. (길이: {len(SOLAR_API_KEY)}, 시작: {SOLAR_API_KEY[:4]}...)" )
else:
    print("⚠️ API 키를 로드하지 못했습니다. .env 파일을 확인해주세요.")
if TTS_KEY:
    print(f"✅ Google STT API 키(TTS_KEY)가 성공적으로 로드되었습니다.")
else:
    print("⚠️ Google STT API 키(TTS_KEY)를 로드하지 못했습니다. .env 파일을 확인해주세요.")
# --- 디버깅 코드 끝 ---


# ==================== 전역 변수 및 설정 ====================

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# add middleware
app.add_middleware(SizeLimitMiddleware, max_size=7*1024*1024) # 7MB limit to request

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
chat_sessions = redis.Redis(host='localhost', port=21101, db=0)
''' redis sorted set
chat:messages:{room_id} => json
{
    "messsage_id": message_id,
    "time": timestamp,
    "role": role,
    "user_id": user_id,
    "message": text,
}
'''

chat_users = redis.Redis(host='localhost', port=21101, db=1)
''' redis set
chat:{room_id} => json
{
    "relink",
    "goranipie"
}
'''

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
    room_id: str
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
    history_string = "\n".join([f"{'상담가' if msg['role'] == 'assistant' else '사용자'}: {msg['message']}" for msg in conversation_history])
    
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
        "당신은 주어진 대화 내용을 바탕으로 감정이 담긴 일기를 작성하고, 특정 감정 점수를 분석하는 전문가입니다. "
        "대화의 핵심 내용을 요약하여, 사용자의 경험과 감정이 잘 드러나는 자연스러운 일기 형식의 글을 작성해주세요. "
        "응답은 반드시 다음 형식에 맞춰 각 항목을 줄바꿈으로 구분해야 합니다.\n"
        "제목: [여기에 20자 내외의 일기 제목 작성]\n"
        "내용:\n"
        "[여기에 3~4문단으로 구성된 일기 본문 작성]\n"
        "감정: [기쁨, 평온, 걱정, 슬픔, 화남 중 가장 적절한 감정 하나만 텍스트로 작성]\n"
        "--- 감정 점수 분석 ---\n"
        "우울감: [0부터 100 사이의 정수 점수]\n"
        "소외감: [0부터 100 사이의 정수 점수]\n"
        "좌절감: [0부터 100 사이의 정수 점수]"
    )
    
    history_string = "\n".join([f"{'상담가' if msg['role'] == 'assistant' else '사용자'}: {msg['message']}" for msg in conversation_history])

    user_prompt = f"""
    다음은 사용자와 상담가 간의 대화 내용입니다.
    ---
    {history_string}
    ---
    위 대화 내용을 바탕으로, 시스템 프롬프트의 지시에 따라 일기와 감정 점수를 생성해주세요.
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
        
        # 생성된 텍스트에서 제목, 내용, 감정 및 점수 파싱
        lines = diary_text.strip().split('\n')
        
        parsed_data = {'content': []}
        is_content_section = False

        for line in lines:
            line_stripped = line.strip()
            if line_stripped.startswith("제목:"):
                parsed_data['title'] = line_stripped.replace("제목:", "").strip()
                is_content_section = False
            elif line_stripped.startswith("내용:"):
                is_content_section = True
            elif line_stripped.startswith("감정:"):
                parsed_data['emotion'] = line_stripped.replace("감정:", "").strip()
                is_content_section = False
            elif line_stripped.startswith("우울감:"):
                parsed_data['depression'] = int(line_stripped.replace("우울감:", "").strip())
            elif line_stripped.startswith("소외감:"):
                parsed_data['isolation'] = int(line_stripped.replace("소외감:", "").strip())
            elif line_stripped.startswith("좌절감:"):
                parsed_data['frustration'] = int(line_stripped.replace("좌절감:", "").strip())
            elif is_content_section and "--- 감정 점수 분석 ---" not in line_stripped:
                parsed_data['content'].append(line)

        title = parsed_data.get('title', "자동 생성된 일기")
        content = "\n".join(parsed_data.get('content', ["내용을 생성하지 못했습니다."])).strip()
        emotion_text = parsed_data.get('emotion', "기쁨")
        
        depression_score = parsed_data.get('depression', 0)
        isolation_score = parsed_data.get('isolation', 0)
        frustration_score = parsed_data.get('frustration', 0)

        emotion_map = {'기쁨': '😊', '평온': '😌', '걱정': '😟', '슬픔': '😢', '화남': '😠'}
        emotion = emotion_map.get(emotion_text, "😊")
        
        save_diary_entry(
            title, content, emotion, user_id, datetime.datetime.now(datetime.timezone.utc),
            depression=depression_score,
            isolation=isolation_score,
            frustration=frustration_score
        )
        print(f"✅ Diary with emotion scores automatically saved for user {user_id}")

    except Exception as e:
        print(f"❌ 일기 생성 또는 저장 중 오류 발생: {e}")
        fallback_content = "대화를 바탕으로 일기를 생성하는 데 실패했습니다.\n\n" + history_string
        save_diary_entry(
            "일기 생성 실패", fallback_content, "😟", user_id, 
            datetime.datetime.now(datetime.timezone.utc)
        )


def send_message(room_id, user_id, text, role):
    key = f"chat:messages:{room_id}"
    timestamp = time.time() # sort with time(=score) (redis sorted set)
    message_id = str(uuid_utils.uuid7())
    
    data = json.dumps({
        "messsage_id": message_id,
        "time": timestamp,
        "role": role,
        "user_id": user_id,
        "message": text,
    })
    print("전송할 메시지 :\n" + data)
    chat_sessions.zadd(key, {data: timestamp})
    print("send_message 호출 및 chat_sessions.zadd 완료")
    keys = chat_sessions.keys('*')
    for key in keys:
        print(key)
    
    return True
    
def get_messages(room_id, cnt=12):
    print("서버에서 채팅 가져오는중...")
    key = f"chat:messages:{room_id}"
    
    raw = chat_sessions.zrevrange(key, 0, cnt - 1)
    messages = [json.loads(msg) for msg in raw]
    messages.reverse()
    print(messages)
    return messages

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

@app.exception_handler(FilesSizeTooLargeError)
async def file_too_large_exception_hander(request: Request, exc: FilesSizeTooLargeError):
    # when voice file is too large(=expensive) to transcribe
    return JSONResponse({"transcript" : "파일이 너무 큽니다."})

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
    room_id = str(uuid_utils.uuid7())
    chat_session_key = f"chat:messages:{room_id}"
    message_id = str(uuid_utils.uuid7())
    
    print(f"첫 채팅 시작 room_id: {room_id}")
    
    # 안정적인 대화 시작을 위해 첫 질문은 고정된 값으로 사용
    first_question = "안녕하세요! 오늘 하루는 어떠셨나요?"
    
    send_message(room_id, user_id, first_question, "assistant")
    chat_users.sadd(f"chat:participants:{room_id}", user_id)
    # 대화 기록 초기화 및 첫 메시지 저장 (role: 'assistant'로 변경)
    
    return JSONResponse(content={"response": first_question, "finished": False, "room_id": room_id})



@app.post("/chat/message")
async def post_chat_message(request: Request, user_message: ChatMessage):
    """사용자 메시지를 처리하고 다음 AI 응답을 반환합니다."""
    current_user = get_current_user(request)
    if not current_user:
        return JSONResponse(status_code=401, content={"error": "Authentication required"})
    
    user_id = current_user.get("id")
    room_id = user_message.room_id
    key = f"chat:messages:{room_id}"

    if chat_sessions.exists(key) == 0:
        return JSONResponse(status_code=400, content={"error": "채팅 세션이 시작되지 않았습니다."})
    
    if not chat_users.sismember(f"chat:participants:{room_id}", user_id):
        print(chat_users.smembers(f"chat:participants:{room_id}"))
        return JSONResponse(status_code=400, content={"error": "채팅에 접근할 권한이 부족합니다."})
    
    if user_message.message == "채팅방 나가기":
        print(f"도중에 끊긴 대화 내역 삭제\n  room_id: {room_id}")
        if chat_sessions.exists(key) == 1 or chat_users.exists(f"chat:participants:{room_id}"):
            chat_sessions.delete(key)
            chat_users.delete(f"chat:participants:{room_id}")
        return
        

    # 현재 대화 기록에 사용자 메시지 추가
    print(f"redis 사용자 채팅 추가 시작 : {user_message.message}")
    send_message(room_id, user_id, user_message.message, "user")
    print(f"redis 사용자 채팅 추가 완료 : {user_message.message}")
    current_conversation = get_messages(room_id, 30)
    
    # AI에게 다음 질문 생성 요청 (await 추가)
    ai_message = await get_ai_question(current_conversation)
    
    # AI 응답을 대화 기록에 추가 (role: 'assistant'로 변경)
    send_message(room_id, user_id, ai_message, "assistant")

    # 대화 종료 시 일기 자동 생성 및 세션 정리
    if ai_message.get("finished"):
        # 백그라운드에서 일기 생성 및 저장 실행 (응답이 사용자에게 즉시 가도록)
        await generate_and_save_diary(user_id, current_conversation)
        if chat_sessions.exists(key) == 1 or chat_users.exists(f"chat:participants:{room_id}"):
            chat_sessions.delete(key)
            chat_users.delete(f"chat:participants:{room_id}")
        
    return JSONResponse(content=ai_message)



@app.post("/chat/transcribe")
async def transcribe_audio(audio_file: UploadFile):
    if not audio_file or not audio_file.filename:
        return JSONResponse({"transcript": "음성 파일을 받지 못했습니다."}, status_code=400)
    
    print(f"전송받은 음성파일 사이즈 : {audio_file.size} byte")
    
    api_key = TTS_KEY # Google STT에 TTS_KEY 사용
    if not api_key:
        print("⚠️ Google STT API 키 (TTS_KEY)를 로드하지 못했습니다. .env 파일을 확인해주세요.")
        return JSONResponse({"transcript": "음성 인식 서비스 키가 설정되지 않았습니다."}, status_code=500)

    audio_content = await audio_file.read()
    base64_audio = base64.b64encode(audio_content).decode('utf-8')

    payload = {
        "config": {
            "encoding": "WEBM_OPUS",
            "languageCode": "ko-KR",
            "enableAutomaticPunctuation": True
        },
        "audio": {
            "content": base64_audio
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GOOGLE_STT_URL}?key={api_key}",
                json=payload,
                timeout=60.0
            )
            response.raise_for_status()
            
            response_data = response.json()
            # Google STT can return an empty response if no speech is detected
            if 'results' in response_data and len(response_data['results']) > 0:
                transcript = response_data['results'][0]['alternatives'][0]['transcript']
            else:
                transcript = "" # No speech detected, return empty string
            
            print(f"Google STT 결과: {transcript}")
            return JSONResponse({"transcript": transcript})

    except httpx.HTTPStatusError as e:
        print(f"Google STT API 오류: {e.response.text}")
        return JSONResponse({"transcript": "음성을 텍스트로 변환하는 데 실패했습니다."}, status_code=500)
    except Exception as e:
        print(f"음성 처리 중 알 수 없는 오류 발생: {e}")
        return JSONResponse({"transcript": "음성 처리 중 알 수 없는 오류가 발생했습니다."}, status_code=500)
    
    

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