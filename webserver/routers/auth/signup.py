from fastapi import Request, APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from ...shared import *
from fastapi import Request, Form
import bcrypt
import datetime
from .email_verification import verify_email_verification_token


# ============= router =============

router = APIRouter()

@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    """회원가입 페이지를 표시합니다."""
    return templates.TemplateResponse("signup.html", {"request": request})

@router.post("/signup")
async def signup(request: Request, 
                email: str = Form(...),
                id: str = Form(...), 
                name: str = Form(...), 
                password: str = Form(...), 
                password_confirm: str = Form(...), 
                birthday: str = Form(...),
                verification_token: str = Form(...)):
    """이메일 인증 후 회원가입 완료"""
    
    token_data = verify_email_verification_token(verification_token)
    if not token_data or token_data.get("email") != email:
        return templates.TemplateResponse("signup.html", {
            "request": request, 
            "error": "이메일 인증이 유효하지 않습니다. 다시 인증을 진행해 주세요."
        })
    
    # 2. 유효성 검사
    if password != password_confirm:
        return templates.TemplateResponse("signup.html", {"request": request, "error": "비밀번호가 일치하지 않습니다."})
    if len(password) < 8:
        return templates.TemplateResponse("signup.html", {"request": request, "error": "비밀번호는 8자 이상이어야 합니다."})
    
    # 3. 중복 확인
    if users.find_one({"id": id}):
        return templates.TemplateResponse("signup.html", {"request": request, "error": "이미 사용 중인 아이디입니다."})
    if users.find_one({"email": email}):
        return templates.TemplateResponse("signup.html", {"request": request, "error": "이미 가입된 이메일입니다."})

    # 4. 스키마에 맞게 데이터 가공
    try:
        new_user = {
            "id": id,
            "name": name,
            "email": email,
            "password": bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode("utf-8"),
            "birthday": datetime.datetime.strptime(birthday, "%Y-%m-%d"),
            "account_type": 0,
            "email_verified": True,
            "created_at": datetime.datetime.now(datetime.timezone.utc)
        }
    except Exception as e:
        print(f"Data processing error during signup: {e}")
        return templates.TemplateResponse("signup.html", {"request": request, "error": "입력된 정보가 올바르지 않습니다."})

    # 5. 데이터베이스에 저장
    try:
        users.insert_one(new_user)
    except Exception as e:
        print(f"DB insertion error during signup: {e}")
        return templates.TemplateResponse("signup.html", {"request": request, "error": "회원가입 중 서버 오류가 발생했습니다."})

    # 6. 성공 응답
    return templates.TemplateResponse("signup.html", {
        "request": request, 
        "success": "회원가입이 완료되었습니다! 로그인 페이지로 이동하여 로그인해 주세요."
    })
    

@router.post("/api/check-id-duplicate")
async def check_id_duplicate(request: Request, id: str = Form(...)):
    """아이디 중복 확인 API"""
    try:
        # check ID duplication
        if users.find_one({"id": id}):
            return JSONResponse(content={"available": False, "message": "이미 사용 중인 아이디입니다."})
        
        # check if ID is valid (basic validation)
        if len(id.strip()) < 4:
            return JSONResponse(content={"available": False, "message": "아이디는 4자 이상이어야 합니다."})
        
        return JSONResponse(content={"available": True, "message": "사용 가능한 아이디입니다."})
        
    except Exception as e:
        print(f"아이디 중복 확인 오류: {e}")
        return JSONResponse(content={"available": False, "message": "아이디 중복 확인 중 오류가 발생했습니다."}, status_code=500)