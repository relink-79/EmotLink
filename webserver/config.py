from pydantic_settings import BaseSettings
from pydantic import SecretStr
import os
from dotenv import load_dotenv
from pydantic_settings import SettingsConfigDict


# This file contains the server configuration
# such as api keys, SMTP info, etc


class ServerConfig(BaseSettings):
    SECRET_KEY: str = "" # jwt secret key
    SOLAR_API_KEY: str = ""
    GOOGLE_STT_KEY: str = ""
    SOLAR_API_URL: str = "https://api.upstage.ai/v1/solar/chat/completions"
    GOOGLE_STT_URL: str = "https://speech.googleapis.com/v1/speech:recognize"
    
    # self-hosted model info
    SELF_HOSTED_MODEL_URL: str = "http://relink79.com/api/stream"
    SELF_HOSTED_API_KEY: str = ""
    
    # smtp info
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = ""
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_PORT: int = 587
    
    # public base url for links in emails and external callbacks
    PUBLIC_BASE_URL: str = "https://emotlink.com"
    
    model_config = SettingsConfigDict(
        env_file=[".env", "../.env"],  # 여러 경로 시도
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )



server_config = ServerConfig()
    
for key, value in vars(server_config).items():
    if not key.startswith("__"):
        print(f"{key}: {SecretStr(value)}")

print("Server config loaded. blank = not loaded, *** = loaded")