from .config import *
from fastapi_mail import FastMail, ConnectionConfig
from pymongo import MongoClient
from fastapi.templating import Jinja2Templates
import redis



# This file contains global variables and instances
# such as redis, mongodb, fastmail, jinja2 templates, etc
# that are used throughout the server



# SMTP
MAIL_USERNAME = server_config.MAIL_USERNAME
MAIL_PASSWORD = SecretStr(server_config.MAIL_PASSWORD)
MAIL_FROM = server_config.MAIL_FROM
MAIL_SERVER = server_config.MAIL_SERVER
MAIL_PORT = server_config.MAIL_PORT
mail_config = ConnectionConfig(
    MAIL_USERNAME=MAIL_USERNAME,
    MAIL_PASSWORD=MAIL_PASSWORD,
    MAIL_FROM=MAIL_FROM,
    MAIL_FROM_NAME="EmotLink",
    MAIL_PORT=MAIL_PORT,
    MAIL_SERVER=MAIL_SERVER,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)
fastmail = FastMail(mail_config)



# MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client.emotlink_db
users = db.users
diaries = db.diaries
links = db.links


# Temporal chat sessions
chat_sessions = redis.Redis(host='localhost', port=21101, db=0)
''' redis sorted set
chat:messages:{room_id} => json
{
    "messsage_id": message_id,
    "time": timestamp,
    "role": role,
    "user_id": user_id,
    "message": text,
}
'''



# chat participants
chat_users = redis.Redis(host='localhost', port=21101, db=1)
''' redis set
chat:{room_id} => json
{
    "relink",
    "goranipie"
}
'''



# email verification status
email_verification_cache = redis.Redis(host='localhost', port=21101, db=2)
''' redis string
email_verified:{email} => json
{
    "token": verification_token,
    "email": email,
    "verified_at": timestamp
}
'''



# jinja2 templates
templates = Jinja2Templates(directory="templates")