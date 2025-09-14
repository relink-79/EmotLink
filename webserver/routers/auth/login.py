import datetime
from jose import jwt
from ...config import *
from fastapi import Request, APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Request, Form
from typing import Optional
from ...shared import *
import bcrypt

SECRET_KEY = server_config.SECRET_KEY


def create_login_token(data: dict, expire = 120) -> str:
    user = data.copy()
    user.update({"expire" : int((datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=expire)).timestamp())})
    return jwt.encode(user, SECRET_KEY, "HS256")

def check_password(password: str, hashed_password: str) -> bool:
    """
    Args:
        password (str) : plain password
        hashed_password (str) : hashed password stored in db
    Note:
        python String uses unicode, but bcrypt uses bytes."""
    return bcrypt.checkpw(password.encode("utf-8"),
                          hashed_password.encode("utf-8"))



# ============= router =============

router = APIRouter()

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None):
    """로그인 페이지를 표시합니다."""
    error_message = None
    if error == "invalid_credentials":
        error_message = "잘못된 사용자 이름 또는 비밀번호입니다."
    elif error == "email_not_verified":
        error_message = "이메일 인증이 완료되지 않았습니다. 이메일을 확인해 주세요."
    else:
        error_message = None
        
    return templates.TemplateResponse("login.html", {
        "request": request, 
        "error": error_message
    })

@router.post("/login")
async def login(request: Request, id: str = Form(...), password: str = Form(...), remember: Optional[bool] = Form(None), dev_mode: Optional[bool] = Form(None)):
    """사용자 로그인을 처리합니다."""
    print("로그인 시도 감지")
    
    # find user by email
    current_user = users.find_one({"email": id})

    # 일반 로그인
    if (id != None) and \
    (password != None) and \
    (current_user != None) and \
    (check_password(password, current_user.get("password"))):
        
        # check email verified
        if not current_user.get("email_verified", False):
            return RedirectResponse(url="/login?error=email_not_verified", status_code=303)
        
        # 토큰에 포함할 사용자 정보 생성
        user_info_for_token = {
            "id": current_user.get("id"),
            "name": current_user.get("name"),
            "email": current_user.get("email"),
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
    return RedirectResponse(url="/login?error=invalid_credentials", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    """사용자 세션을 지워 로그아웃합니다."""
    response = RedirectResponse(url="/login")
    response.delete_cookie("login_token")
    return response