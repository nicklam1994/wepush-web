"""
速率限制中間件
=============
基於內存的 IP 速率限制器，僅對 /push/send 端點生效。

特性：
- 默認限制：每個 IP 每分鐘 5 次請求（可配置）
- 超限時返回 429 狀態碼及人類可讀的提示信息
- 使用滑動窗口計數器（簡單實現）
"""

import time
import threading
import logging
from collections import defaultdict
from typing import DefaultDict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, HTMLResponse
from starlette.requests import Request

from config import RATELIMIT_MAX_REQUESTS, RATELIMIT_WINDOW_SECS

logger = logging.getLogger(__name__)

# 受限路徑（精確匹配）
_LIMITED_PATH = "/push/send"

# ── 內存存儲：{ ip: [timestamp, ...] } ──────────────────
_store: DefaultDict[str, list[float]] = defaultdict(list)
_lock = threading.Lock()


def _get_client_ip(request: Request) -> str:
    """獲取客戶端真實 IP（考慮反向代理）。"""
    # 優先從 X-Forwarded-For 獲取
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    # 其次從 X-Real-IP 獲取
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    # 最後使用直接 IP
    if request.client:
        return request.client.host
    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    IP 速率限制中間件。

    只對 /push/send 端點實施限制。
    """

    async def dispatch(self, request: Request, call_next):
        # 只限制特定路徑
        if request.url.path != _LIMITED_PATH:
            return await call_next(request)

        ip = _get_client_ip(request)
        now = time.time()

        with _lock:
            # 清理過期記錄（超出時間窗口的）
            cutoff = now - RATELIMIT_WINDOW_SECS
            _store[ip] = [ts for ts in _store[ip] if ts > cutoff]

            # 檢查是否超限
            if len(_store[ip]) >= RATELIMIT_MAX_REQUESTS:
                # 計算重試時間
                oldest = min(_store[ip])
                retry_after = int(oldest + RATELIMIT_WINDOW_SECS - now)

                logger.warning(
                    f"Rate limit exceeded: IP={ip}, "
                    f"count={len(_store[ip])}/{RATELIMIT_MAX_REQUESTS} "
                    f"in {RATELIMIT_WINDOW_SECS}s"
                )

                return _build_429_response(retry_after, ip)

            # 記錄本次請求
            _store[ip].append(now)

        return await call_next(request)


def _build_429_response(retry_after: int, ip: str) -> HTMLResponse:
    """構建 429 Too Many Requests 響應。"""
    html = _RATELIMIT_HTML_TEMPLATE.format(
        max_requests=RATELIMIT_MAX_REQUESTS,
        window_secs=RATELIMIT_WINDOW_SECS,
        retry_after=retry_after,
        ip=ip,
    )
    response = HTMLResponse(content=html, status_code=429)
    response.headers["Retry-After"] = str(max(retry_after, 1))
    return response


# ── 429 錯誤頁面模板 ──────────────────────────────────────
_RATELIMIT_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>請求過於頻繁 - WePush Web</title>
    <link href="https://cdn.bootcdn.net/ajax/libs/bootstrap/5.3.3/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{
            background: #0f1117; color: #e1e4e8;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            min-height: 100vh; display: flex; align-items: center; justify-content: center;
        }}
        .limit-card {{
            background: #161b22; border: 1px solid #30363d;
            border-radius: 12px; padding: 40px; max-width: 500px; text-align: center;
        }}
        .limit-card h1 {{ font-size: 20px; margin-bottom: 12px; }}
        .limit-card p {{ color: #8b949e; font-size: 13px; margin-bottom: 8px; }}
        .limit-card .countdown {{
            font-size: 32px; font-weight: 700; color: #f78166;
            margin: 16px 0;
        }}
        .limit-card .info {{
            font-size: 11px; color: #6e7681; margin-top: 12px;
        }}
    </style>
</head>
<body>
    <div class="limit-card">
        <h1>⏱️ 請求過於頻繁</h1>
        <p>你的 IP 在 {window_secs} 秒內發送了超過 {max_requests} 次推送請求，已被暫時限制。</p>
        <div class="countdown" id="countdown">{retry_after}</div>
        <p>秒後可重試</p>
        <p class="info">IP: {ip}</p>
        <a href="/push" class="btn btn-outline-secondary mt-3">← 返回推送頁面</a>
    </div>
    <script>
        (function() {{
            var el = document.getElementById('countdown');
            var secs = parseInt(el.textContent, 10);
            if (isNaN(secs) || secs <= 0) return;
            var timer = setInterval(function() {{
                secs--;
                el.textContent = secs;
                if (secs <= 0) {{
                    clearInterval(timer);
                    el.textContent = '0';
                    location.reload();
                }}
            }}, 1000);
        }})();
    </script>
</body>
</html>"""
