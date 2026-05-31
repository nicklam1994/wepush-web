"""
CSRF 防護中間件
===============
對所有 POST 請求實施 Double Submit Cookie 模式的 CSRF 防護。

工作原理：
1. 每個請求檢查 Cookie 中是否有 `csrf_token`
2. 若無，則生成一個隨機 token 並設置到 Cookie
3. POST 請求時，要求表單中攜帶同名 `csrf_token` 字段
4. 比對 Cookie 與表單值，一致則放行

排除路徑：
- /api/* — API 端點（通常由 Token/Auth Header 保護）
- /login — 登錄頁面本身
"""

import secrets
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse, Response
from starlette.requests import Request

logger = logging.getLogger(__name__)

# Cookie / 表單字段名稱
_CSRF_COOKIE = "csrf_token"
_CSRF_FIELD = "csrf_token"

# 排除 CSRF 檢查的路徑前綴
_EXCLUDE_PREFIXES = (
    "/api/",
    "/login",
    "/static/",
)

# CSRF Token 在模板上下文中的變量名
_CONTEXT_KEY = "csrf_token"


def _is_excluded(path: str) -> bool:
    """判斷路徑是否排除 CSRF 檢查。"""
    for prefix in _EXCLUDE_PREFIXES:
        if path == prefix or path.startswith(prefix):
            return True
    return False


class CSRFTokenInjectorMiddleware(BaseHTTPMiddleware):
    """
    在每個 HTML 響應中注入 CSRF token。

    通過在 </form> 標籤前插入 hidden input 來實現。
    同時將 token 設置到 Cookie 中。
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # 只在 HTML 響應中注入
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            return response

        # 確保 cookie 中有 csrf_token
        csrf_token = request.cookies.get(_CSRF_COOKIE)
        if not csrf_token:
            csrf_token = secrets.token_hex(32)

        # 讀取響應體 — 使用 Response.body_iterator（Starlette 內部屬性）
        try:
            body = b""
            async for chunk in response.body_iterator:  # type: ignore[attr-defined]
                body += chunk

            # 在每個 </form> 前注入 hidden input
            injected_html = body.decode("utf-8", errors="replace")
            injected_html = injected_html.replace(
                "</form>",
                f'<input type="hidden" name="{_CSRF_FIELD}" value="{csrf_token}"></form>',
            )

            new_response = HTMLResponse(
                content=injected_html,
                status_code=response.status_code,
                headers=dict(response.headers),
            )
            new_response.set_cookie(
                key=_CSRF_COOKIE,
                value=csrf_token,
                httponly=False,
                samesite="lax",
                path="/",
            )
            return new_response
        except Exception:
            # 如果讀取 body 失敗，直接返回原始響應並設置 cookie
            response.set_cookie(
                key=_CSRF_COOKIE,
                value=csrf_token,
                httponly=False,
                samesite="lax",
                path="/",
            )
            return response


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF 驗證中間件 — 對 POST/PUT/PATCH/DELETE 請求校驗 token。

    必須放在 CSRFTokenInjectorMiddleware 之後。
    """

    async def dispatch(self, request: Request, call_next):
        # 只檢查寫操作
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return await call_next(request)

        path = request.url.path

        # 排除路徑跳過
        if _is_excluded(path):
            return await call_next(request)

        # 讀取 Cookie 中的 token
        cookie_token = request.cookies.get(_CSRF_COOKIE)

        # 讀取表單中的 token
        content_type = request.headers.get("content-type", "")
        form_token: str | None = None

        if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            try:
                form = await request.form()
                raw = form.get(_CSRF_FIELD)
                if isinstance(raw, str):
                    form_token = raw
            except Exception:
                pass

        # 也檢查 JSON body 中的 csrf_token
        if not form_token and "application/json" in content_type:
            try:
                body = await request.json()
                if isinstance(body, dict):
                    raw = body.get(_CSRF_FIELD)
                    if isinstance(raw, str):
                        form_token = raw
            except Exception:
                pass

        # 驗證
        if not cookie_token or not form_token:
            logger.warning(
                f"CSRF: 缺少 token (cookie={bool(cookie_token)}, form={bool(form_token)}) — {path}"
            )
            return HTMLResponse(
                content=_CSRF_ERROR_HTML.format(path=path),
                status_code=403,
            )

        if not secrets.compare_digest(cookie_token, form_token):
            logger.warning(f"CSRF: token 不匹配 — {path}")
            return HTMLResponse(
                content=_CSRF_ERROR_HTML.format(path=path),
                status_code=403,
            )

        return await call_next(request)


# ── CSRF 錯誤頁面 ─────────────────────────────────────────
_CSRF_ERROR_HTML = """<!DOCTYPE html>
<html lang="zh-CN" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CSRF 驗證失敗 - WePush Web</title>
    <link href="https://cdn.bootcdn.net/ajax/libs/bootstrap/5.3.3/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{
            background: #0f1117; color: #e1e4e8;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            min-height: 100vh; display: flex; align-items: center; justify-content: center;
        }}
        .error-card {{
            background: #161b22; border: 1px solid #30363d;
            border-radius: 12px; padding: 40px; max-width: 500px; text-align: center;
        }}
        .error-card h1 {{ font-size: 20px; margin-bottom: 12px; }}
        .error-card p {{ color: #8b949e; font-size: 13px; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <div class="error-card">
        <h1>⚠️ CSRF 驗證失敗</h1>
        <p>請求未通過安全校驗，請返回上一頁並重新提交表單。</p>
        <p style="font-size:11px;color:#6e7681;">路徑: {path}</p>
        <a href="javascript:history.back()" class="btn btn-outline-secondary">← 返回上一頁</a>
    </div>
</body>
</html>"""
