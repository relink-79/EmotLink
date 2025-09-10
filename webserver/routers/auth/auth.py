from fastapi import Request, APIRouter
from typing import Optional
from jose import jwt
from ...config import *
from ...shared import *

SECRET_KEY = server_config.SECRET_KEY



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

