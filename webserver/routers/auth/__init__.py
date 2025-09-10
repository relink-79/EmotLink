from .auth import *
from . import login, signup, email_verification

auth_router = APIRouter()
auth_router.include_router(login.router)
auth_router.include_router(signup.router)
auth_router.include_router(email_verification.router)
