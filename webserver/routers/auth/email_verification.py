import datetime
from jose import jwt, JWTError
from ...config import *
from ...shared import *
from fastapi_mail import MessageSchema, MessageType
from fastapi import Request, APIRouter
from fastapi.responses import JSONResponse
from fastapi import Request, Form
import json

SECRET_KEY = server_config.SECRET_KEY


def create_email_verification_token(email: str, user_data: dict, expire_minutes: int = 30):
    expire_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=expire_minutes)
    temp_user = {
        "email": email,
        "user_data": user_data,
        "exp": expire_time,
        "type": "email_verification"
    }
    return jwt.encode(temp_user, SECRET_KEY, "HS256")

def verify_email_verification_token(token: str) -> dict | None:
    try:
        tmp_user = jwt.decode(token, SECRET_KEY, "HS256")
        if tmp_user.get("type") != "email_verification":
            return None
        else:
            return tmp_user
    except JWTError:
        return None

async def send_verification_email(email: str, verification_token: str):
    base_url = server_config.PUBLIC_BASE_URL.rstrip("/") if hasattr(server_config, "PUBLIC_BASE_URL") else "https://emotlink.com"
    verification_url = f"{base_url}/verify-email?token={verification_token}"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>EmotLink 이메일 인증</title>
    </head>
    <body style="margin: 0; padding: 20px; font-family: Arial, sans-serif; background-color: #f5f5f5;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px;">
            <tr>
                <td style="background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                    
                    <!-- Header with Logo -->
                    <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%">
                        <tr>
                            <td align="center" style="padding-bottom: 30px;">
                                <!-- Logo Circle -->
                                <table align="center" border="0" cellpadding="0" cellspacing="0">
                                    <tr>
                                        <td align="center" style="width: 60px; height: 60px; background-color: #4f46e5; border-radius: 50%; text-align: center; vertical-align: middle; color: white; font-size: 24px; line-height: 60px; margin-bottom: 15px;">
                                            🔗
                                        </td>
                                    </tr>
                                </table>
                                <h1 style="color: #333; margin: 15px 0 10px 0; font-size: 24px; font-weight: bold;">EmotLink 이메일 인증</h1>
                            </td>
                        </tr>
                    </table>
                    
                    <!-- Content -->
                    <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%">
                        <tr>
                            <td style="color: #666; line-height: 1.6; margin-bottom: 30px; padding-bottom: 30px;">
                                <p style="margin: 0 0 15px 0;">안녕하세요!</p>
                                <p style="margin: 0 0 15px 0;">EmotLink 회원가입을 위해 이메일 인증이 필요합니다.</p>
                                <p style="margin: 0;">아래 버튼을 클릭하여 이메일 인증을 완료해 주세요.</p>
                            </td>
                        </tr>
                    </table>
                    
                    <!-- Button -->
                    <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%">
                        <tr>
                            <td align="center" style="padding: 30px 0;">
                                <table border="0" cellpadding="0" cellspacing="0">
                                    <tr>
                                        <td align="center" style="background-color: #4f46e5; border-radius: 5px;">
                                            <a href="{verification_url}" style="display: inline-block; padding: 15px 30px; font-family: Arial, sans-serif; font-size: 16px; font-weight: bold; color: #ffffff !important; text-decoration: none; border-radius: 5px;">이메일 인증하기</a>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                    </table>
                    
                    <!-- Footer -->
                    <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%">
                        <tr>
                            <td style="border-top: 1px solid #eee; padding-top: 20px; margin-top: 30px; text-align: center;">
                                <p style="color: #999; font-size: 12px; margin: 0 0 10px 0;">이 링크는 30분 후 만료됩니다.</p>
                                <p style="color: #999; font-size: 12px; margin: 0;">만약 본인이 회원가입을 신청하지 않으셨다면, 이 메일을 무시해 주세요.</p>
                            </td>
                        </tr>
                    </table>
                    
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    message = MessageSchema(
        subject="EmotLink 이메일 인증",
        recipients=[email],
        body=html_body,
        subtype=MessageType.html
    )
    
    await fastmail.send_message(message)
    
    
    
# ============= router =============

router = APIRouter()
    
@router.post("/send-verification")
async def send_verification(request: Request, email: str = Form(...)):
    try:
        # check email dup
        if users.find_one({"email": email}):
            return JSONResponse(
                status_code=400, 
                content={"success": False, "message": "이미 가입된 이메일입니다."}
            )
        
        # temporal user token (no user data, similar to provisional registration)
        verification_token = create_email_verification_token(email, {})
        
        await send_verification_email(email, verification_token)
        
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "인증 메일이 발송되었습니다. 이메일을 확인해 주세요."}
        )
        
    except Exception as e:
        print(f"이메일 발송 오류: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "이메일 발송 중 오류가 발생했습니다."}
        )

@router.get("/verify-email")
async def verify_email(request: Request, token: str):
    token_data = verify_email_verification_token(token)
    if not token_data:
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "error": "인증 링크가 유효하지 않거나 만료되었습니다. 다시 시도해 주세요."
        })
    
    email = token_data.get("email")
    
    # if already exists
    if users.find_one({"email": email}):
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "error": "이미 가입된 이메일입니다."
        })
    
    # save verification status in Redis
    verification_key = f"email_verified:{email}"
    verification_data = {
        "token": token,
        "email": email,
        "verified_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    email_verification_cache.setex(verification_key, 1800, json.dumps(verification_data))  # 30분 TTL
    
    # show success page
    return templates.TemplateResponse("email_verified.html", {
        "request": request,
        "email_verified": True,
        "email": email,
        "verification_token": token,
        "success": "이메일 인증이 완료되었습니다!"
    })

@router.get("/api/check-verification")
async def check_verification_status(request: Request, email: str):
    try:
        # check email duplication
        if users.find_one({"email": email}):
            return JSONResponse(content={"verified": False, "message": "이미 가입된 이메일입니다."})
        
        # check verification status from redis
        verification_key = f"email_verified:{email}"
        if email_verification_cache.exists(verification_key):
            verification_data = json.loads(email_verification_cache.get(verification_key))
            return JSONResponse(content={
                "verified": True, 
                "email": email,
                "verification_token": verification_data.get("token")
            })
        
        return JSONResponse(content={"verified": False})
        
    except Exception as e:
        print(f"인증 상태 확인 오류: {e}")
        return JSONResponse(content={"verified": False}, status_code=500)