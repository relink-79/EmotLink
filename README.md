# EmotLink

FastAPI와 Capacitor를 사용하는 웹/앱 프로젝트입니다.

## 설치 (최초 1회)

```bash
git clone https://github.com/relink-79/EmotLink.git
cd EmotLink
python setup.py
```

`setup.py` 실행 후, 열려있는 모든 터미널을 껐다가 다시 켜주세요.

## 실행

개발 목적에 따라 아래 중 하나를 실행합니다.

#### 모바일 앱 개발

```bash
python run_app.py
```

#### 웹 브라우저 개발

```bash
python -m uvicorn webserver.main:app --reload
```
웹 브라우저에서 `http://127.0.0.1:8000` 주소로 접속하여 확인합니다.
