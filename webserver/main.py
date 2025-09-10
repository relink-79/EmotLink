from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
import datetime

# 서버 로직 분리 모듈
from .web_middleware import *
from .routers.auth import *
from .routers.emoter import *

# Global variables & instances
# this includes api keys, redis, mongodb, fastmail, jinja2 templates, etc
from .shared import *
from .config import *


from .routers.emoter.diary import get_emotion_stats




# load api keys from config
SECRET_KEY = server_config.SECRET_KEY
SOLAR_API_KEY = server_config.SOLAR_API_KEY
GOOGLE_STT_KEY = server_config.GOOGLE_STT_KEY # Google STT 키 로드
SOLAR_API_URL = server_config.SOLAR_API_URL
GOOGLE_STT_URL = server_config.GOOGLE_STT_URL



# ==================== 전역 변수 및 설정 ====================

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# add middleware
app.add_middleware(SizeLimitMiddleware, max_size=7*1024*1024) # 7MB limit to request

    

DATETIME_STR_FORMAT = "%Y.%m.%d %H:%M" # ex) "2025.07.01 00:08"

# 로거 설정 (터미널에 에러를 기록)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== 페이지 라우트들 ====================

# login, signup, email verification, etc
app.include_router(auth_router, prefix="", tags=["Authentication"])

# Emoter's AI Chat, diary, stats, etc
app.include_router(emoter_router, prefix="", tags=["Emoter"])

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

