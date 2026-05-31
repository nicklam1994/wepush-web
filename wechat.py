"""WeChat API integration - token management & template message sending."""
import time
import threading
import json
import httpx
from typing import Optional

# Thread-safe token cache
_token_lock = threading.Lock()
_token_cache: dict = {
    "access_token": None,
    "expires_at": 0,
}


async def get_access_token(appid: str, appsecret: str) -> Optional[str]:
    """Get WeChat access_token with simple caching (thread-safe)."""
    now = time.time()

    with _token_lock:
        if _token_cache["access_token"] and _token_cache["expires_at"] > now + 60:
            return _token_cache["access_token"]

    url = "https://api.weixin.qq.com/cgi-bin/token"
    params = {"grant_type": "client_credential", "appid": appid, "secret": appsecret}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params)
        data = resp.json()

    if "access_token" in data:
        with _token_lock:
            _token_cache["access_token"] = data["access_token"]
            _token_cache["expires_at"] = now + data.get("expires_in", 7200) - 300
        return _token_cache["access_token"]
    else:
        raise Exception(f"获取 access_token 失败: {data.get('errmsg', str(data))}")


async def send_template_message(
    appid: str,
    appsecret: str,
    openid: str,
    template_id: str,
    data: dict,
    url: str = "",
    miniprogram: Optional[dict] = None,
) -> dict:
    """Send a WeChat template message to a single user."""
    token = await get_access_token(appid, appsecret)

    body = {
        "touser": openid,
        "template_id": template_id,
        "data": data,
    }
    if url:
        body["url"] = url
    if miniprogram:
        body["miniprogram"] = miniprogram

    api_url = f"https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={token}"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(api_url, json=body)
        result = resp.json()

    return result


def build_template_data(data_fields: list, values: dict) -> dict:
    """
    根据模板字段定义 + 实际值, 构建微信要求的 data 结构

    data_fields: [{"name":"first","value":"您好","color":"#000000"}, ...]
    values: {"first":"实际标题", "keyword1":"实际内容", ...}
    """
    result = {}
    for field in data_fields:
        name = field.get("name", "")
        default_value = field.get("value", "")
        color = field.get("color", "#000000")
        actual_value = values.get(name, default_value)
        result[name] = {"value": actual_value, "color": color}
    return result


def get_wechat_template_example() -> list:
    """返回一個示例模板字段結構，方便用戶參考"""
    return [
        {"name": "first", "value": "您好，您有一條新消息", "color": "#000000"},
        {"name": "keyword1", "value": "消息內容", "color": "#173177"},
        {"name": "keyword2", "value": "2024-01-01", "color": "#173177"},
        {"name": "remark", "value": "感謝您的關注", "color": "#000000"},
    ]
