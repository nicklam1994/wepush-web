"""APScheduler-based scheduled task system."""
import asyncio
import json
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from database import SessionLocal
from models import Task, PushHistory, Template, Recipient, WechatAccount
from models import decrypt_secret
from wechat import send_template_message, build_template_data
from apis import resolve_data_source

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def execute_push_task(task_id: int):
    """
    Execute a scheduled push task.
    This is called by the APScheduler job.
    """
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id, Task.is_active == True).first()
        if not task:
            logger.warning(f"Task {task_id} not found or inactive")
            return

        template = db.query(Template).filter(Template.id == task.template_id).first()
        if not template:
            logger.warning(f"Template {task.template_id} not found")
            return

        account = db.query(WechatAccount).filter(WechatAccount.is_active == True).first()
        if not account:
            logger.warning("No active WeChat account configured")
            return

        # 解析接收人
        recipients = []
        if isinstance(task.recipient_ids, list):
            recipients = db.query(Recipient).filter(
                Recipient.id.in_(task.recipient_ids)
            ).all()
        if not recipients:
            logger.warning(f"No recipients found for task {task_id}")
            return

        # 解析數據源
        variables = {}
        if task.data_source and task.data_source != "manual":
            variables = await resolve_data_source(task.data_source, task.data_config or {})

        # 應用變量映射
        final_vars = {}
        var_mapping = task.var_mapping or {}
        for field in (template.data_fields or []):
            name = field.get("name", "")
            default_value = field.get("value", "")
            # 先看映射
            mapped_key = var_mapping.get(name, "")
            if mapped_key and mapped_key in variables:
                final_vars[name] = variables[mapped_key]
            else:
                final_vars[name] = default_value

        # 發送
        data = build_template_data(template.data_fields or [], final_vars)
        miniprogram = None
        if template.ma_appid and template.ma_page_path:
            miniprogram = {"appid": template.ma_appid, "pagepath": template.ma_page_path}

        success_count = 0
        fail_count = 0
        details = []

        appsecret = decrypt_secret(account.appsecret)

        for r in recipients:
            try:
                result = await send_template_message(
                    appid=account.appid,
                    appsecret=appsecret,
                    openid=r.openid,
                    template_id=template.template_id,
                    data=data,
                    url=template.url or "",
                    miniprogram=miniprogram,
                )
                if result.get("errcode") == 0:
                    success_count += 1
                    details.append({"openid": r.openid, "status": "success"})
                else:
                    fail_count += 1
                    details.append({
                        "openid": r.openid,
                        "status": "fail",
                        "error": result.get("errmsg", "未知错误"),
                    })
            except Exception as e:
                fail_count += 1
                details.append({"openid": r.openid, "status": "fail", "error": str(e)})

        # 記錄歷史
        total = len(recipients)
        status = "success" if fail_count == 0 else ("partial" if success_count > 0 else "fail")

        history = PushHistory(
            task_id=task.id,
            task_name=task.name,
            template_name=template.name,
            trigger_type="cron",
            total_count=total,
            success_count=success_count,
            fail_count=fail_count,
            details=details,
            status=status,
        )
        db.add(history)
        task.last_run = datetime.now()
        db.commit()

        logger.info(f"Task {task_id} done: {success_count}/{total} success")

    except Exception as e:
        logger.error(f"Task {task_id} error: {e}")
    finally:
        db.close()


def sync_push_manual(
    template_id: int,
    recipient_ids: list,
    variables: dict,
    db_session,
) -> dict:
    """
    Synchronous wrapper for manual push (called from web route).
    Used for one-off manual pushes.
    """
    return asyncio.run(
        _manual_push_async(template_id, recipient_ids, variables, db_session)
    )


async def _manual_push_async(
    template_id: int,
    recipient_ids: list,
    variables: dict,
    db_session,
) -> dict:
    """Async manual push implementation."""
    template = db_session.query(Template).filter(Template.id == template_id).first()
    if not template:
        return {"error": "模板不存在"}

    account = db_session.query(WechatAccount).filter(WechatAccount.is_active == True).first()
    if not account:
        return {"error": "沒有配置有效的微信賬號"}

    # Normalize to list
    if not isinstance(recipient_ids, list):
        recipient_ids = [recipient_ids]
    recipients = db_session.query(Recipient).filter(
        Recipient.id.in_(recipient_ids)
    ).all() if recipient_ids else []

    if not recipients:
        return {"error": "沒有選擇接收人"}

    data = build_template_data(template.data_fields or [], variables)
    miniprogram = None
    if template.ma_appid and template.ma_page_path:
        miniprogram = {"appid": template.ma_appid, "pagepath": template.ma_page_path}

    success_count = 0
    fail_count = 0
    details = []

    appsecret = decrypt_secret(account.appsecret)

    for r in recipients:
        try:
            result = await send_template_message(
                appid=account.appid,
                appsecret=appsecret,
                openid=r.openid,
                template_id=template.template_id,
                data=data,
                url=template.url or "",
                miniprogram=miniprogram,
            )
            if result.get("errcode") == 0:
                success_count += 1
                details.append({"openid": r.openid, "status": "success"})
            else:
                fail_count += 1
                details.append({
                    "openid": r.openid,
                    "status": "fail",
                    "error": result.get("errmsg", "未知错误"),
                })
        except Exception as e:
            fail_count += 1
            details.append({"openid": r.openid, "status": "fail", "error": str(e)})

    total = len(recipients)
    status = "success" if fail_count == 0 else ("partial" if success_count > 0 else "fail")

    history = PushHistory(
        task_id=0,
        task_name="手动推送",
        template_name=template.name,
        trigger_type="manual",
        total_count=total,
        success_count=success_count,
        fail_count=fail_count,
        details=details,
        status=status,
    )
    db_session.add(history)
    db_session.commit()

    return {
        "status": status,
        "total": total,
        "success": success_count,
        "fail": fail_count,
        "details": details,
    }


def init_scheduler():
    """Load all active tasks from DB and register them with APScheduler."""
    if scheduler.running:
        return

    db = SessionLocal()
    try:
        tasks = db.query(Task).filter(Task.is_active == True).all()
        for task in tasks:
            try:
                trigger = CronTrigger.from_crontab(task.cron_expr)
                scheduler.add_job(
                    execute_push_task,
                    trigger=trigger,
                    id=f"task_{task.id}",
                    args=[task.id],
                    replace_existing=True,
                    name=task.name,
                    misfire_grace_time=300,
                )
                logger.info(f"Registered cron job: {task.name} ({task.cron_expr})")
            except Exception as e:
                logger.error(f"Failed to register task {task.id}: {e}")
    finally:
        db.close()

    scheduler.start()
    logger.info("Scheduler started")


def refresh_task(task_id: int):
    """Add or update a single task in the scheduler."""
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return

        job_id = f"task_{task.id}"

        if task.is_active:
            trigger = CronTrigger.from_crontab(task.cron_expr)
            scheduler.add_job(
                execute_push_task,
                trigger=trigger,
                id=job_id,
                args=[task.id],
                replace_existing=True,
                name=task.name,
                misfire_grace_time=300,
            )
            logger.info(f"Refreshed job: {task.name}")
        else:
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
                logger.info(f"Removed job: {task.name}")
    finally:
        db.close()


def remove_task_job(task_id: int):
    """Remove a task from the scheduler."""
    job_id = f"task_{task_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
