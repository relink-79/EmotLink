import requests
import json
import os
from dotenv import load_dotenv

# 1. .env에서 API 키 로드
load_dotenv()
API_KEY = os.getenv("API_KEY")

# 2. 사용자 입력 받기
user_input = input("질문을 입력하세요: ")

# 3. API URL 및 헤더 설정
API_URL = "https://api.upstage.ai/v1/solar/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

# 4. 프롬프트 메시지 구성
messages = [
    {
        "role": "system",
        "content": (
            "사람과 같은 말투로 대답해야 합니다"
        )
    },
    {
        "role": "user",
        "content": f"""사용자의 대답: "{user_input}"

이 대답을 보고 일기를 작성해주세요.
일기 내용은 길게 써주세요. 하지만 반드시 없는 내용을 추가해서 작성하면 안됩니다.

결과는 아래 JSON 형식처럼 출력해 주세요:

{{
  "일기": "일기 내용"
}}


설명 없이 JSON만 출력해 주세요.
"""
    }
]

# 5. Payload 구성 (JSON만 출력하도록 유도)
payload = {
    "model": "solar-1-mini-chat",
    "messages": messages,
    "temperature": 0.2,
    "top_p": 0.9,
    "n": 1,
    "stream": False
}

# 6. API 요청
response = requests.post(API_URL, headers=headers, json=payload)

# 7. 결과 처리
if response.status_code == 200:
    result = response.json()
    message = result["choices"][0]["message"]["content"]
    print("\n🧠 LLM 응답 (원문):\n", message)

    try:
        parsed_json = json.loads(message)
        print("\n✅ 파싱된 JSON:\n", json.dumps(parsed_json, indent=2, ensure_ascii=False))
    except json.JSONDecodeError:
        print("\n⚠️ 응답이 JSON 형식이 아닙니다.")
else:
    print(f"\n❌ 오류 발생: {response.status_code}\n{response.text}")
