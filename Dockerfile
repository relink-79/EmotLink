FROM python:3.11-slim

WORKDIR /app

# 파이썬 의존성 설치
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 소스코드 복사
COPY . /app

# uvicorn 실행을 위한 환경변수
ENV PYTHONUNBUFFERED=1

# 컨테이너 내부에서 8000번 포트 개방
EXPOSE 8000

# 서버 실행
CMD ["python", "-m", "uvicorn", "webserver.main:app", "--host", "0.0.0.0", "--port", "8000"]
