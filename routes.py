"""FastAPI web routes for WePush Web."""
import json
import logging
import os
from datetime import datetime
from typing import Optional

import jinja2
from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models import WechatAccount, Template, Recipient, Task, PushHistory
from wechat import build_template_data, get_wechat_template_example
from apis import resolve_data_source, fetch_weather_hko, fetch_amap_weather, fetch_amap_poi
from scheduler import sync_push_manual, refresh_task, remove_task_job

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(_BASE_DIR, "templates")),
    auto_reload=True,
    cache_size=50,
)

router = APIRouter()
templates = Jinja2Templates(env=_jinja_env)


# ─── 首頁儀表板 ──────────────────────────────────────
@router.get("/")
async def index(request: Request, db: Session = Depends(get_db)):
    account = db.query(WechatAccount).first()
    template_count = db.query(Template).count()
    recipient_count = db.query(Recipient).count()
    task_count = db.query(Task).count()
    active_task_count = db.query(Task).filter(Task.is_active == True).count()
    recent_history = (
        db.query(PushHistory).order_by(desc(PushHistory.created_at)).limit(10).all()
    )
    total_pushed = db.query(PushHistory).count()
    total_success = db.query(PushHistory).with_entities(
        PushHistory.success_count
    ).all()
    total_success_sum = sum(s[0] for s in total_success)

    return templates.TemplateResponse(request, "index.html", {
        "request": request,
        "account": account,
        "template_count": template_count,
        "recipient_count": recipient_count,
        "task_count": task_count,
        "active_task_count": active_task_count,
        "recent_history": recent_history,
        "total_pushed": total_pushed,
        "total_success": total_success_sum,
        "page": "dashboard",
    })


# ─── 帳號配置 ────────────────────────────────────────
@router.get("/settings")
async def settings_page(request: Request, db: Session = Depends(get_db)):
    account = db.query(WechatAccount).first()
    return templates.TemplateResponse(request, "settings.html", {
        "request": request,
        "account": account,
        "page": "settings",
    })


@router.post("/settings/account")
async def save_account(
    request: Request,
    name: str = Form("默认账号"),
    appid: str = Form(...),
    appsecret: str = Form(...),
    db: Session = Depends(get_db),
):
    account = db.query(WechatAccount).first()
    if account:
        account.name = name
        account.appid = appid
        account.appsecret = appsecret
        account.updated_at = datetime.now()
    else:
        account = WechatAccount(name=name, appid=appid, appsecret=appsecret)
        db.add(account)
    db.commit()
    return RedirectResponse(url="/settings", status_code=303)


# ─── 模板管理 ────────────────────────────────────────
@router.get("/templates")
async def template_list(request: Request, db: Session = Depends(get_db)):
    items = db.query(Template).order_by(desc(Template.updated_at)).all()
    return templates.TemplateResponse(request, "templates.html", {
        "request": request,
        "templates": items,
        "page": "templates",
    })


@router.get("/templates/new")
async def template_new(request: Request):
    example = get_wechat_template_example()
    return templates.TemplateResponse(request, "template_form.html", {
        "request": request,
        "template": None,
        "example": json.dumps(example, ensure_ascii=False),
        "page": "templates",
    })


@router.get("/templates/{tid}/edit")
async def template_edit(request: Request, tid: int, db: Session = Depends(get_db)):
    item = db.query(Template).filter(Template.id == tid).first()
    if not item:
        return RedirectResponse(url="/templates", status_code=302)
    return templates.TemplateResponse(request, "template_form.html", {
        "request": request,
        "template": item,
        "example": json.dumps(item.data_fields or [], ensure_ascii=False),
        "page": "templates",
    })


@router.post("/templates/save")
async def template_save(
    request: Request,
    tid: Optional[int] = Form(None),
    name: str = Form(...),
    template_id: str = Form(...),
    url: str = Form(""),
    ma_appid: str = Form(""),
    ma_page_path: str = Form(""),
    data_fields: str = Form("[]"),
    remark: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        fields = json.loads(data_fields)
    except json.JSONDecodeError:
        fields = []

    if tid:
        item = db.query(Template).filter(Template.id == tid).first()
        if item:
            item.name = name
            item.template_id = template_id
            item.url = url
            item.ma_appid = ma_appid
            item.ma_page_path = ma_page_path
            item.data_fields = fields
            item.remark = remark
            item.updated_at = datetime.now()
    else:
        item = Template(
            name=name,
            template_id=template_id,
            url=url,
            ma_appid=ma_appid,
            ma_page_path=ma_page_path,
            data_fields=fields,
            remark=remark,
        )
        db.add(item)

    db.commit()
    return RedirectResponse(url="/templates", status_code=303)


@router.post("/templates/{tid}/delete")
async def template_delete(tid: int, db: Session = Depends(get_db)):
    item = db.query(Template).filter(Template.id == tid).first()
    if item:
        db.delete(item)
        db.commit()
    return RedirectResponse(url="/templates", status_code=303)


# ─── 接收人管理 ──────────────────────────────────────
@router.get("/recipients")
async def recipient_list(request: Request, db: Session = Depends(get_db)):
    items = db.query(Recipient).order_by(desc(Recipient.created_at)).all()
    return templates.TemplateResponse(request, "recipients.html", {
        "request": request,
        "recipients": items,
        "page": "recipients",
    })


@router.post("/recipients/save")
async def recipient_save(
    request: Request,
    rid: Optional[int] = Form(None),
    nickname: str = Form(""),
    openid: str = Form(...),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    if rid:
        item = db.query(Recipient).filter(Recipient.id == rid).first()
        if item:
            item.nickname = nickname
            item.openid = openid
            item.note = note
    else:
        existing = db.query(Recipient).filter(Recipient.openid == openid).first()
        if existing:
            existing.nickname = nickname or existing.nickname
            existing.note = note or existing.note
        else:
            item = Recipient(nickname=nickname, openid=openid, note=note)
            db.add(item)
    db.commit()
    return RedirectResponse(url="/recipients", status_code=303)


@router.post("/recipients/{rid}/delete")
async def recipient_delete(rid: int, db: Session = Depends(get_db)):
    item = db.query(Recipient).filter(Recipient.id == rid).first()
    if item:
        db.delete(item)
        db.commit()
    return RedirectResponse(url="/recipients", status_code=303)


# ─── 定時任務管理 ────────────────────────────────────
@router.get("/tasks")
async def task_list(request: Request, db: Session = Depends(get_db)):
    items = db.query(Task).order_by(desc(Task.updated_at)).all()
    templates_list = db.query(Template).order_by(Template.name).all()
    recipients_list = db.query(Recipient).order_by(Recipient.nickname).all()
    return templates.TemplateResponse(request, "tasks.html", {
        "request": request,
        "tasks": items,
        "templates": templates_list,
        "recipients": recipients_list,
        "page": "tasks",
    })


@router.post("/tasks/save")
async def task_save(
    request: Request,
    task_id: Optional[int] = Form(None),
    name: str = Form(...),
    template_id: int = Form(...),
    recipient_ids: str = Form("[]"),
    cron_expr: str = Form("0 8 * * *"),
    data_source: str = Form("manual"),
    data_config: str = Form("{}"),
    var_mapping: str = Form("{}"),
    is_active: bool = Form(True),
    db: Session = Depends(get_db),
):
    try:
        rids = json.loads(recipient_ids)
        dcfg = json.loads(data_config)
        vmap = json.loads(var_mapping)
    except json.JSONDecodeError:
        rids, dcfg, vmap = [], {}, {}

    if task_id:
        item = db.query(Task).filter(Task.id == task_id).first()
        if item:
            item.name = name
            item.template_id = template_id
            item.recipient_ids = rids
            item.cron_expr = cron_expr
            item.data_source = data_source
            item.data_config = dcfg
            item.var_mapping = vmap
            item.is_active = is_active
            item.updated_at = datetime.now()
            db.commit()
            refresh_task(item.id)
    else:
        item = Task(
            name=name,
            template_id=template_id,
            recipient_ids=rids,
            cron_expr=cron_expr,
            data_source=data_source,
            data_config=dcfg,
            var_mapping=vmap,
            is_active=is_active,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        refresh_task(item.id)

    return RedirectResponse(url="/tasks", status_code=303)


@router.post("/tasks/{tid}/toggle")
async def task_toggle(tid: int, db: Session = Depends(get_db)):
    item = db.query(Task).filter(Task.id == tid).first()
    if item:
        item.is_active = not item.is_active
        db.commit()
        refresh_task(item.id)
    return RedirectResponse(url="/tasks", status_code=303)


@router.post("/tasks/{tid}/delete")
async def task_delete(tid: int, db: Session = Depends(get_db)):
    item = db.query(Task).filter(Task.id == tid).first()
    if item:
        db.delete(item)
        db.commit()
        remove_task_job(tid)
    return RedirectResponse(url="/tasks", status_code=303)


# ─── 手動推送 ────────────────────────────────────────
@router.get("/push")
async def push_page(request: Request, db: Session = Depends(get_db)):
    templates_list = db.query(Template).order_by(Template.name).all()
    recipients_list = db.query(Recipient).order_by(Recipient.nickname).all()
    return templates.TemplateResponse(request, "push.html", {
        "request": request,
        "templates": templates_list,
        "recipients": recipients_list,
        "page": "push",
    })


@router.post("/push/send")
async def push_send(
    request: Request,
    template_id: int = Form(...),
    recipient_ids: str = Form("[]"),
    var_values: str = Form("{}"),
    db: Session = Depends(get_db),
):
    try:
        rids = json.loads(recipient_ids)
        values = json.loads(var_values)
    except json.JSONDecodeError:
        return RedirectResponse(url="/push", status_code=303)

    result = sync_push_manual(
        template_id=template_id,
        recipient_ids=rids,
        variables=values,
        db_session=db,
    )

    if "error" in result:
        return templates.TemplateResponse(request, "push.html", {
            "request": request,
            "templates": db.query(Template).order_by(Template.name).all(),
            "recipients": db.query(Recipient).order_by(Recipient.nickname).all(),
            "error": result["error"],
            "page": "push",
        })

    return templates.TemplateResponse(request, "push.html", {
        "request": request,
        "templates": db.query(Template).order_by(Template.name).all(),
        "recipients": db.query(Recipient).order_by(Recipient.nickname).all(),
        "result": result,
        "page": "push",
    })


# ─── 推送歷史 ────────────────────────────────────────
@router.get("/history")
async def history_list(
    request: Request,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    per_page = 20
    offset = (page - 1) * per_page
    items = (
        db.query(PushHistory)
        .order_by(desc(PushHistory.created_at))
        .offset(offset)
        .limit(per_page)
        .all()
    )
    total = db.query(PushHistory).count()
    total_pages = max(1, (total + per_page - 1) // per_page)

    return templates.TemplateResponse(request, "history.html", {
        "request": request,
        "history": items,
        "page_num": page,
        "total_pages": total_pages,
        "page": "history",
    })


@router.get("/history/{hid}")
async def history_detail(hid: int, request: Request, db: Session = Depends(get_db)):
    item = db.query(PushHistory).filter(PushHistory.id == hid).first()
    if not item:
        return RedirectResponse(url="/history", status_code=302)
    return templates.TemplateResponse(request, "history_detail.html", {
        "request": request,
        "h": item,
        "page": "history",
    })


# ─── API 測試端點 ──────────────────────────────────
@router.get("/api/test/weather")
async def test_weather():
    """測試天氣 API，返回當前天氣數據"""
    data = await fetch_weather_hko()
    return JSONResponse({"status": "ok" if data else "fail", "data": data})


@router.get("/api/templates/{tid}/preview")
async def template_preview(tid: int, db: Session = Depends(get_db)):
    """預覽模板字段結構"""
    item = db.query(Template).filter(Template.id == tid).first()
    if not item:
        return JSONResponse({"error": "模板不存在"}, status_code=404)

    fields = item.data_fields or []
    example_data = {}
    for f in fields:
        example_data[f["name"]] = f"示例{f['value']}"

    built = build_template_data(fields, example_data)
    return JSONResponse({"fields": fields, "example_data": built})
