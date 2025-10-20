from fastapi import Request, APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from ...shared import templates, users, links
from ..auth.auth import get_current_user
from .diary import get_emotion_stats_for_user, get_health_indicator_for_user
import datetime

router = APIRouter()


def require_linker(current_user):
    return current_user and (current_user.get("role") == "linker" or current_user.get("account_type") == 1)


@router.get("/emoters", response_class=HTMLResponse)
async def emoters_page(request: Request):
    """Linker가 연결한 Emoter 목록 + 추가 폼"""
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    if not require_linker(current_user):
        return RedirectResponse(url="/", status_code=303)

    linker_id = current_user.get("id")
    # find linked emoters
    linked = list(links.find({"linker_id": linker_id}))
    emoter_ids = [l.get("emoter_id") for l in linked]
    status_map = {l.get("emoter_id"): l.get("status", "pending") for l in linked}
    emoter_list = []
    health_map = {}
    if emoter_ids:
        cursor = users.find({"id": {"$in": emoter_ids}}, {"password": 0})
        emoter_list = list(cursor)
        # 각 emoter의 건강 인디케이터 계산
        for u in emoter_list:
            uid = u.get("id")
            if not uid:
                continue
            try:
                health_map[uid] = get_health_indicator_for_user(uid)
            except Exception:
                health_map[uid] = {"color": "green", "delta": 0.0}

    return templates.TemplateResponse("emoters.html", {
        "request": request,
        "current_user": current_user,
        "emoters": emoter_list,
        "status_map": status_map,
        "health_map": health_map,
        "message": None,
        "error": None,
    })


@router.post("/emoters/add")
async def add_emoter_link(request: Request):
    """Linker가 Emoter를 추가"""
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    if not require_linker(current_user):
        return RedirectResponse(url="/", status_code=303)

    form = await request.form()
    target = (form.get("emoter_id") or "").strip()

    if not target:
        return RedirectResponse(url="/emoters", status_code=303)

    # find emoter by id or email
    emoter = users.find_one({"$or": [{"id": target}, {"email": target}]})
    if not emoter:
        return RedirectResponse(url="/emoters", status_code=303)
    if emoter.get("account_type", 0) != 0:
        return RedirectResponse(url="/emoters", status_code=303)

    linker_id = current_user.get("id")
    emoter_id = emoter.get("id")
    # create pending link or keep accepted
    existing = links.find_one({"linker_id": linker_id, "emoter_id": emoter_id})
    if existing and existing.get("status") == "accepted":
        pass  # already accepted, do nothing
    else:
        links.update_one(
            {"linker_id": linker_id, "emoter_id": emoter_id},
            {"$set": {
                "linker_id": linker_id,
                "emoter_id": emoter_id,
                "status": "pending",
                "created_at": existing.get("created_at") if existing else datetime.datetime.now(datetime.timezone.utc),
                "updated_at": datetime.datetime.now(datetime.timezone.utc),
            }},
            upsert=True
        )

    return RedirectResponse(url="/emoters", status_code=303)


@router.get("/emoters/{emoter_id}/stats", response_class=HTMLResponse)
async def view_linked_emoter_stats(request: Request, emoter_id: str):
    """연결된 Emoter의 감정스코어 보기"""
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    if not require_linker(current_user):
        return RedirectResponse(url="/", status_code=303)

    # check link exists
    linker_id = current_user.get("id")
    link = links.find_one({"linker_id": linker_id, "emoter_id": emoter_id})
    if not link or link.get("status") != "accepted":
        return RedirectResponse(url="/emoters", status_code=303)

    # fetch emoter user info
    emoter = users.find_one({"id": emoter_id}, {"password": 0})
    if not emoter:
        return RedirectResponse(url="/emoters", status_code=303)

    stats = get_emotion_stats_for_user(emoter_id)

    return templates.TemplateResponse("stats_linker.html", {
        "request": request,
        "current_user": current_user,
        "emoter": emoter,
        "stats": stats,
    })


@router.get("/links/requests", response_class=HTMLResponse)
async def requests_page(request: Request):
    """Emoter가 받은 친구 요청/연결 관리"""
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    # only emoter
    if current_user.get("account_type", 0) != 0:
        return RedirectResponse(url="/", status_code=303)

    emoter_id = current_user.get("id")
    pending = list(links.find({"emoter_id": emoter_id, "status": "pending"}))
    accepted = list(links.find({"emoter_id": emoter_id, "status": "accepted"}))
    # fetch linker user info for both lists
    linker_map = {}
    linker_ids = []
    if pending:
        linker_ids.extend([p.get("linker_id") for p in pending])
    if accepted:
        linker_ids.extend([a.get("linker_id") for a in accepted])
    if linker_ids:
        unique_ids = list(set(linker_ids))
        for u in users.find({"id": {"$in": unique_ids}}, {"password": 0}):
            linker_map[u["id"]] = u

    return templates.TemplateResponse("requests.html", {
        "request": request,
        "current_user": current_user,
        "pending": pending,
        "accepted": accepted,
        "linker_map": linker_map,
    })


@router.post("/links/requests/{linker_id}/accept")
async def accept_request(request: Request, linker_id: str):
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    if current_user.get("account_type", 0) != 0:
        return RedirectResponse(url="/", status_code=303)
    emoter_id = current_user.get("id")
    links.update_one(
        {"linker_id": linker_id, "emoter_id": emoter_id},
        {"$set": {"status": "accepted", "updated_at": datetime.datetime.now(datetime.timezone.utc)}}
    )
    return RedirectResponse(url="/links/requests", status_code=303)


@router.post("/links/requests/{linker_id}/decline")
async def decline_request(request: Request, linker_id: str):
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    if current_user.get("account_type", 0) != 0:
        return RedirectResponse(url="/", status_code=303)
    emoter_id = current_user.get("id")
    # either delete or set declined
    links.update_one(
        {"linker_id": linker_id, "emoter_id": emoter_id},
        {"$set": {"status": "declined", "updated_at": datetime.datetime.now(datetime.timezone.utc)}}
    )
    return RedirectResponse(url="/links/requests", status_code=303)


@router.post("/links/{linker_id}/remove")
@router.get("/links/{linker_id}/remove")
@router.post("/links/{linker_id}/remove/")
@router.get("/links/{linker_id}/remove/")
async def remove_link_as_emoter(request: Request, linker_id: str):
    """Emoter가 기존 연결(accepted/pending/declined)을 삭제"""
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    if current_user.get("account_type", 0) != 0:
        return RedirectResponse(url="/", status_code=303)
    emoter_id = current_user.get("id")
    links.delete_one({"linker_id": linker_id, "emoter_id": emoter_id})
    return RedirectResponse(url="/links/requests", status_code=303)


@router.post("/emoters/{emoter_id}/remove")
@router.get("/emoters/{emoter_id}/remove")
@router.post("/emoters/{emoter_id}/remove/")
@router.get("/emoters/{emoter_id}/remove/")
async def remove_link_as_linker(request: Request, emoter_id: str):
    """Linker가 기존 연결을 삭제/요청 취소"""
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    if not require_linker(current_user):
        return RedirectResponse(url="/", status_code=303)
    linker_id = current_user.get("id")
    links.delete_one({"linker_id": linker_id, "emoter_id": emoter_id})
    return RedirectResponse(url="/emoters", status_code=303)
