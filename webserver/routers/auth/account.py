from fastapi import Request, APIRouter
from fastapi.responses import RedirectResponse
from ...shared import diaries, links, users
from .auth import get_current_user

router = APIRouter()


@router.post("/account/delete")
async def delete_account(request: Request):
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    user_id = current_user.get("id")
    if not user_id:
        return RedirectResponse(url="/settings", status_code=303)

    try:
        #delete all data related to the user
        diaries.delete_many({"author_id": user_id})
        links.delete_many({"emoter_id": user_id})
        links.delete_many({"linker_id": user_id})
        users.delete_one({"id": user_id})
    except Exception:
        response = RedirectResponse(url="/login", status_code=303)
        response.delete_cookie("login_token")
        return response

    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("login_token")
    return response


