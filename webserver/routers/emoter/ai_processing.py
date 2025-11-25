from ...shared import *
from ...config import *
import datetime
import httpx
from typing import List
from urllib.parse import urlparse

from .diary import save_diary_entry


SOLAR_API_KEY = server_config.SOLAR_API_KEY
SOLAR_API_URL = "https://api.upstage.ai/v1/solar/chat/completions"


async def get_ai_question(conversation_history: List[dict], model: str = "solar-pro") -> dict:
    """Solar API 또는 Self-Hosted API를 호출하여 다음 질문 또는 최종 메시지를 생성합니다."""
    
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
            "모든 답변은 부드럽고 자연스러운 한국어 대화체(높임말)로 해주세요. 질문만 툭 던지는 느낌을 주면 안 됩니다."
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
        "top_p": 0.9,
        "n": 1,
        "stream": False
    }

    # Flag to determine if we should use solar (initially true if model != emotlink-model)
    use_solar = (model != "emotlink-model")
    
    if model == "emotlink-model":
        try:
            # Self-Hosted Model Logic (OpenAI Compatible)
            # Construct URL: extract base (scheme + netloc) and append /v1/chat/completions
            parsed_url = urlparse(server_config.SELF_HOSTED_MODEL_URL)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            api_url = f"{base_url}/v1/chat/completions"
            
            api_key = server_config.SELF_HOSTED_API_KEY
            
            # Override headers for self-hosted model
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-API-Key": api_key,
            }
            
            # Reformat messages for the self-hosted model
            messages_payload = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # Adjust payload for self-hosted model with guardrails disabled
            payload = {
                "model": "/model",
                "messages": messages_payload,
                "stream": False, 
                "max_tokens": 1024,
                "disable_guardrails": True,
                "disable_reasoning_filter": True,
            }
            
            print(f"Sending request to Self-Hosted Model: {api_url}")
            async with httpx.AsyncClient() as client:
                response = await client.post(api_url, headers=headers, json=payload, timeout=60.0)
                
                if response.status_code != 200:
                    print(f"Self-Hosted API Error: {response.status_code} - {response.text}")
                    print("Falling back to Solar API...")
                    use_solar = True
                else:
                    try:
                        response_data = response.json()
                        if "choices" in response_data:
                            ai_response = response_data["choices"][0]["message"]["content"]
                        else:
                            ai_response = str(response_data)
                            
                        if "END_CHAT" in ai_response:
                            return {"response": ai_response.replace("END_CHAT", "").strip(), "finished": True}
                        else:
                            return {"response": ai_response, "finished": False}
                    except:
                        ai_response = response.text
                        print("Failed to parse self-hosted response, falling back to Solar")
                        use_solar = True

        except Exception as e:
            print(f"Self-Hosted Model Exception: {e}")
            print("Falling back to Solar API...")
            use_solar = True

    if use_solar:
        try:
            # Default: Solar Pro Logic
            # Reset headers for Solar
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {SOLAR_API_KEY}"
            }
            
            # Reset payload for Solar
            payload = {
                "model": "solar-1-mini-chat",
                "messages": messages,
                "temperature": 0.5,
                "top_p": 0.9,
                "n": 1,
                "stream": False
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(SOLAR_API_URL, headers=headers, json=payload, timeout=30.0)
                response.raise_for_status()
                ai_response = response.json()["choices"][0]["message"]["content"]
        
            if "END_CHAT" in ai_response:
                return {"response": ai_response.replace("END_CHAT", "").strip(), "finished": True}
            else:
                return {"response": ai_response, "finished": False}
        except httpx.RequestError as e:
            print(f"API 호출 오류 (Solar): {e}")
            return {"response": "죄송합니다, AI 모델과 통신하는 중 오류가 발생했어요. 잠시 후 다시 시도해주세요.", "finished": True}
    
    return {"response": "오류가 발생했습니다.", "finished": False}


async def generate_and_save_diary(user_id: str, conversation_history: List[dict], model: str = "solar-pro"):
    """Solar API 또는 Self-Hosted API를 호출하여 대화 내용 기반으로 일기를 생성하고 저장합니다."""

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

    try:
        # Always use Solar Pro Logic for Diary Generation
        payload = {
            "model": "solar-1-mini-chat",
            "messages": messages,
            "temperature": 0.7,
            "stream": False
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(SOLAR_API_URL, headers=headers, json=payload, timeout=60.0)
            response.raise_for_status()
        
        diary_text = response.json()["choices"][0]["message"]["content"]
        
        # 생성된 텍스트에서 제목, 내용, 감정 및 점수 파싱 (Existing Logic)
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

        # Common Save Logic
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