from fastapi import Request, APIRouter, Form
from fastapi.responses import RedirectResponse, JSONResponse
from ...shared import diaries, links, users, chat_sessions, chat_users
from .auth import get_current_user
from .login import create_login_token

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

        # delete all redis chat sessions that the user participates in
        # scan participants sets and remove related message sorted sets
        for key in chat_users.scan_iter(match="chat:participants:*"):
            k = key.decode() if isinstance(key, (bytes, bytearray)) else str(key)
            if chat_users.sismember(key, user_id):
                room_id = k.split(":")[-1]
                chat_sessions.delete(f"chat:messages:{room_id}")
                chat_users.delete(key)

    except Exception:
        response = RedirectResponse(url="/login", status_code=303)
        response.delete_cookie("login_token")
        return response

    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("login_token")
    return response



@router.post("/account/update-name")
async def update_account_name(request: Request, name: str = Form(...)):
    current_user = get_current_user(request)

    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    user_id = current_user.get("id")

    if not user_id:
        return RedirectResponse(url="/settings", status_code=303)

    # validate name
    new_name = (name or "").strip()
    if len(new_name) < 1 or len(new_name) > 16:
        return JSONResponse(content={"ok": False, "message": "닉네임은 1~16자여야 합니다."})

    users.update_one({"id": user_id}, {"$set": {"name": new_name}})

    updated_user = users.find_one({"id": user_id}) or {}
    acct_type = updated_user.get("account_type", current_user.get("account_type", 0))

    # update login token with new name
    user_info_for_token = {
        "id": updated_user.get("id", current_user.get("id")),
        "name": updated_user.get("name", new_name),
        "email": updated_user.get("email", current_user.get("email")),
        "account_type": acct_type,
        "role": "emoter" if acct_type == 0 else "linker",
    }
    login_token = create_login_token(user_info_for_token)

    response = JSONResponse(content={"ok": True, "name": user_info_for_token["name"]})
    response.set_cookie(
        key="login_token",
        value=login_token,
        httponly=True,
        samesite="lax",
    )
    return response
    