from fastapi import Request, APIRouter
from fastapi.responses import JSONResponse
from fastapi import Request, UploadFile
from ...shared import *
from ...config import *
import base64
import httpx
from ..auth.auth import get_current_user
import time
import uuid_utils
import json
from pydantic import BaseModel
from .ai_processing import *

class ChatMessage(BaseModel):
    room_id: str
    message: str



SOLAR_API_URL = "https://api.upstage.ai/v1/solar/chat/completions"
GOOGLE_STT_URL = "https://speech.googleapis.com/v1/speech:recognize"



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
    chat_sessions.expire(key, 7200) # 2H TTL
    
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



# ============= router =============

router = APIRouter()

@router.post("/chat/start")
async def start_chat(request: Request):
    """채팅 세션을 초기화하고 고정된 첫 질문을 반환합니다."""
    current_user = get_current_user(request)
    if not current_user:
        return JSONResponse(status_code=401, content={"error": "Authentication required"})
    # Linker는 채팅 시작 차단
    if current_user.get("role") == "linker" or current_user.get("account_type") == 1:
        return JSONResponse(status_code=403, content={"error": "forbidden"})
 
    user_id = current_user.get("id")
    room_id = str(uuid_utils.uuid7())
    chat_session_key = f"chat:messages:{room_id}"
    message_id = str(uuid_utils.uuid7())
    
    print(f"첫 채팅 시작 room_id: {room_id}")
    
    # 안정적인 대화 시작을 위해 첫 질문은 고정된 값으로 사용
    first_question = "안녕하세요! 오늘 하루는 어떠셨나요?"
    
    send_message(room_id, user_id, first_question, "assistant")
    if user_id:
        chat_users.sadd(f"chat:participants:{room_id}", user_id)
    chat_users.expire(f"chat:participants:{room_id}", 7200) # 2H TTL
    # 대화 기록 초기화 및 첫 메시지 저장 (role: 'assistant'로 변경)
    
    return JSONResponse(content={"response": first_question, "finished": False, "room_id": room_id})

@router.post("/chat/message")
async def post_chat_message(request: Request, user_message: ChatMessage):
    """사용자 메시지를 처리하고 다음 AI 응답을 반환합니다."""
    current_user = get_current_user(request)
    if not current_user:
        return JSONResponse(status_code=401, content={"error": "Authentication required"})
    # Linker는 메시지 전송 차단
    if current_user.get("role") == "linker" or current_user.get("account_type") == 1:
        return JSONResponse(status_code=403, content={"error": "forbidden"})
    
    user_id = current_user.get("id")
    room_id = user_message.room_id
    key = f"chat:messages:{room_id}"

    if chat_sessions.exists(key) == 0:
        return JSONResponse(status_code=400, content={"error": "채팅 세션이 시작되지 않았습니다."})
    
    if user_id and not chat_users.sismember(f"chat:participants:{room_id}", user_id):
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
    if ai_message.get("finished") and user_id:
        # 백그라운드에서 일기 생성 및 저장 실행 (응답이 사용자에게 즉시 가도록)
        await generate_and_save_diary(user_id, current_conversation)
        if chat_sessions.exists(key) == 1 or chat_users.exists(f"chat:participants:{room_id}"):
            chat_sessions.delete(key)
            chat_users.delete(f"chat:participants:{room_id}")
        
    return JSONResponse(content=ai_message)



@router.post("/chat/transcribe")
async def transcribe_audio(audio_file: UploadFile):
    if not audio_file or not audio_file.filename:
        return JSONResponse({"transcript": "음성 파일을 받지 못했습니다."}, status_code=400)
    
    print(f"전송받은 음성파일 사이즈 : {audio_file.size} byte")
    
    api_key = server_config.GOOGLE_STT_KEY # Google STT에 GOOGLE_STT_KEY 사용
    if not api_key:
        print("⚠️ Google STT API 키 (GOOGLE_STT_KEY)를 로드하지 못했습니다. .env 파일을 확인해주세요.")
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