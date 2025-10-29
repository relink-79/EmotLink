<div align="center">

<h1>EmotLink</h1>

<img src="static/emotlink-logo.svg" alt="EmotLink Logo" width="120" />

대화로 하루를 정리하고, 스스로를 돌보는 감정 다이어리 서비스입니다.<br/>
Emoter(사용자)는 AI와 대화하며 감정과 사건을 정리하고, Linker(보호자/상담자)는 연결이 승인된 사용자에 한해 변화 지표를 살펴볼 수 있습니다. 음성 입력(STT), 이메일 인증, 역할 기반 접근 제어를 포함하여 웹/모바일 환경에서 자연스럽게 사용하도록 설계했습니다.

<br/>

Reflect on your day through conversation and take care of yourself with an emotion diary.<br/>
Emoters talk with AI to organize feelings and events. Linkers (guardians/counselors) can review trends only for users who have approved a connection. The experience is designed to feel natural on web and mobile, with voice input (STT), email verification, and role‑based access control.

<br/>

<a href="https://github.com/relink-79/EmotLink/stargazers"><img alt="GitHub Stars" src="https://img.shields.io/github/stars/relink-79/EmotLink?color=ffd24d" /></a>
<a href="https://github.com/relink-79/EmotLink/network/members"><img alt="GitHub Forks" src="https://img.shields.io/github/forks/relink-79/EmotLink?color=9ecbff" /></a>
<br/>
<img alt="Python" src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white" />
<img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" />
<img alt="MongoDB" src="https://img.shields.io/badge/MongoDB-7+-4EA94B?logo=mongodb&logoColor=white" />
<img alt="Redis" src="https://img.shields.io/badge/Redis-7+-DC382D?logo=redis&logoColor=white" />


<br/>

<a href="https://emotlink.com">
  <img alt="Open EmotLink" src="https://img.shields.io/badge/Open%20EmotLink-emotlink.com-4f46e5?style=for-the-badge" />
</a>



</div>

<details open>
<summary><strong>Table of Contents</strong></summary>

- [🌟 Highlights](#-highlights)
- [✨ Feature Overview](#-feature-overview)
- [🚀 Getting Started](#-getting-started)
- [⚙️ Configuration](#%EF%B8%8F-configuration)
- [📦 Containers](#-containers)
- [🧠 About](#-about)
- [🤝 Contributing](#-contributing)

</details>

## 🌟 Highlights

- ⚡ High‑performance backend with FastAPI and Jinja templates
- 🧩 Integrated MongoDB + Redis for data and caching/session use cases
- 📱 Capacitor integration for Android development workflow (`run_app.py`)
- 🐳 Simple local dev/run via Docker Compose
- 🛡️ Built‑in email verification and login flows

## ✨ Feature Overview

- Authentication: sign‑up, login, and email verification
- AI chat: guided conversation; on finish, auto‑generate and save a diary
- Diary/Stats: store emotion emoji with depression/isolation/frustration scores; summaries
- Linking: Linkers add/request; Emoters accept/decline
- Web/Mobile: template‑based web UI and Capacitor‑powered Android flow

## 🧠 About

- Emoters reflect on the day through AI‑guided conversation; a diary is generated when the chat ends.
- Each diary stores an emotion emoji and three metrics: depression, isolation, frustration.
- Linkers (guardian/counselor roles) can view stats for approved, linked Emoters.

See code: `webserver/main.py:1`, `webserver/routers/emoter/ai_processing.py:1`, `webserver/routers/emoter/diary.py:1`, `webserver/routers/emoter/linker.py:1`

## 🚀 Getting Started

Two ways to run for local development:

1) Python local run (recommended)

```bash
# 1) Clone & enter
git clone https://github.com/relink-79/EmotLink.git
cd EmotLink

# 2) Virtualenv & deps (Python 3.11)
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3) Prepare environment (.env)
cp .env.example .env  # fill values

# 4) Run server (web)
python -m uvicorn webserver.main:app --host 0.0.0.0 --port 8000
# Open: http://127.0.0.1:8000
```

Android development flow:

```bash
# Prereqs: Node.js, Android Studio, Capacitor CLI
python run_app.py  # FastAPI server + Android launcher
```

2) Docker Compose

```bash
docker compose up -d --build
# Web: http://127.0.0.1:8001 (container is 8000)
```

## ⚙️ Configuration

Create a `.env` file at the repo root. Do not commit secrets.

```dotenv
# Server / External APIs
SOLAR_API_KEY=
GOOGLE_STT_KEY=

# SMTP
MAIL_USERNAME=
MAIL_ADDRESS=
MAIL_PASSWORD=
MAIL_FROM=
MAIL_PORT=587

# (Optional) Cloudflare Tunnel
# CF_TUNNEL_TOKEN=
```

Defaults (ports/connections):

- Local run defaults: `MONGO_URL=mongodb://localhost:27017/`, `REDIS_HOST=localhost`, `REDIS_PORT=21101` (from code)
- Docker Compose: container `6379` exposed as host `21102`

Compose service env:

- `MONGO_URL=mongodb://mongo:27017/`
- `REDIS_HOST=redis`
- `REDIS_PORT=6379`

## 📦 Containers

`docker-compose.yml` overview:

- `app`: FastAPI server (ports `8001:8000`)
- `mongo`: MongoDB 7 (host `27018` → container `27017`)
- `redis`: Redis 7 (host `21102` → container `6379`)
- `cloudflared`: optional; requires `CF_TUNNEL_TOKEN`

Commands:

```bash
docker compose up -d     # run in background
docker compose logs -f   # follow logs
docker compose down      # stop & remove
```

## 🤝 Contributing

Issues and PRs are welcome — bug reports, docs, and feature ideas.
