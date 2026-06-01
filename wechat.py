"""WeChat API integration - token management & template message sending."""
import time
import threading
import json
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

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

    # 40001 = token 過期，清緩存重試一次
    if result.get("errcode") == 40001:
        with _token_lock:
            _token_cache["access_token"] = None
            _token_cache["expires_at"] = 0
        token = await get_access_token(appid, appsecret)
        api_url = f"https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={token}"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(api_url, json=body)
            result = resp.json()

    logger.info(f"WeChat send result: errcode={result.get('errcode')}, errmsg={result.get('errmsg')}, msgid={result.get('msgid')}")
    return result


def build_template_data(data_fields: list, values: dict) -> dict:
    """
    根据模板字段定义 + 实际值, 构建微信要求的 data 结构

    data_fields: [{"name":"first","value":"{{temp}}","color":"#000000"}, ...]
    values: {"temp":"30.1°C", "humidity":"72%", ...}

    支援 {{var}} 變量替換：若 default_value 含 {{var}} 且 values 有對應 key，自動替換
    """
    import re

    result = {}
    for field in data_fields:
        name = field.get("name", "")
        default_value = field.get("value", "")
        color = field.get("color", "#000000")

        # 1. 直接匹配：values 中有同名字段
        if name in values and values[name]:
            actual_value = values[name]
        else:
            # 2. 無直接匹配時才用 default_value
            actual_value = default_value

        # 始終對值做 {{var}} 替換（無論來自 values 還是 default）
        if "{{" in actual_value:
            for var_name in re.findall(r"\{\{(\w+)\}\}", actual_value):
                if var_name in values and values[var_name]:
                    actual_value = actual_value.replace(f"{{{{{var_name}}}}}", str(values[var_name]))
                else:
                    actual_value = actual_value.replace(f"{{{{{var_name}}}}}", "")

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
