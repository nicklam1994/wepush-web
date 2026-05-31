"""
認證中間件
=========
簡單的 Token 認證機制：
- 從 config.AUTH_TOKEN 讀取密鑰（優先環境變量 WEPUSH_AUTH_TOKEN）
- 支持 Cookie (`auth_token`) 或 Query Param (`?token=...`) 兩種方式傳遞
- 登錄頁: GET/POST /login  — POST 驗證密碼並設置 Cookie 後跳轉
- 登出: GET /logout — 清除 Cookie
- 靜態文件 /static/* 始終放行
- 若 AUTH_TOKEN 為空/None，完全跳過認證（向後兼容）
"""

import logging
from urllib.parse import urlencode

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse, HTMLResponse
from starlette.requests import Request

from config import AUTH_TOKEN, APP_TITLE

logger = logging.getLogger(__name__)

# ── 公開路徑（不需要認證）─────────────────────────────────
_PUBLIC_PREFIXES = ("/static/", "/login", "/logout")

# 登錄頁面路徑
_LOGIN_PATH = "/login"
_LOGOUT_PATH = "/logout"

# Cookie 名稱
_COOKIE_NAME = "auth_token"

# 登錄表單字段名
_PASSWORD_FIELD = "password"


def _is_public_path(path: str) -> bool:
    """判斷路徑是否為公開路徑（無需認證）。"""
    for prefix in _PUBLIC_PREFIXES:
        if path == prefix or path.startswith(prefix):
            return True
    return False


def _get_auth_token_from_request(request: Request) -> str | None:
    """從請求中提取 auth token。

    優先級：Cookie > Query Param。
    """
    # 從 Cookie 讀取
    token = request.cookies.get(_COOKIE_NAME)
    if token:
        return token

    # 從 query 參數讀取
    token = request.query_params.get("token")
    if token:
        return token

    return None


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Token 認證中間件。

    若 config.AUTH_TOKEN 為空，則所有請求直接放行。
    否則，對非公開路徑檢查 Cookie 或 Query Param 中的 token。
    """

    async def dispatch(self, request: Request, call_next):
        # 檢查是否需要認證
        if not AUTH_TOKEN:
            return await call_next(request)

        path = request.url.path

        # ── 處理登出 ──────────────────────────────────
        if path == _LOGOUT_PATH:
            response = RedirectResponse(url=_LOGIN_PATH, status_code=303)
            response.delete_cookie(_COOKIE_NAME, path="/")
            return response

        # ── 處理登錄頁 GET ────────────────────────────
        if path == _LOGIN_PATH and request.method == "GET":
            # 已登錄則直接跳轉首頁
            token = _get_auth_token_from_request(request)
            if token == AUTH_TOKEN:
                return RedirectResponse(url="/", status_code=303)
            # 顯示登錄表單
            return await self._render_login_page(request, error=None)

        # ── 處理登錄表單 POST ─────────────────────────
        if path == _LOGIN_PATH and request.method == "POST":
            form = await request.form()
            password = form.get(_PASSWORD_FIELD, "")
            if password == AUTH_TOKEN:
                response = RedirectResponse(url="/", status_code=303)
                response.set_cookie(
                    key=_COOKIE_NAME,
                    value=AUTH_TOKEN,
                    httponly=True,
                    samesite="lax",
                    max_age=86400 * 30,  # 30 天
                    path="/",
                )
                return response
            # 密碼錯誤
            return await self._render_login_page(request, error="密碼錯誤，請重試")

        # ── 公開路徑放行 ──────────────────────────────
        if _is_public_path(path):
            return await call_next(request)

        # ── 驗證 token ────────────────────────────────
        token = _get_auth_token_from_request(request)
        if token == AUTH_TOKEN:
            return await call_next(request)

        # ── 未認證 → 跳轉登錄頁 ──────────────────────
        redirect_url = f"{_LOGIN_PATH}?next={request.url.path}"
        return RedirectResponse(url=redirect_url, status_code=303)

    async def _render_login_page(
        self, request: Request, error: str | None = None
    ) -> HTMLResponse:
        """渲染登錄頁面 HTML。"""
        # 使用簡單內聯 HTML，避免依賴模板引擎
        next_path = request.query_params.get("next", "/")

        html = _LOGIN_HTML_TEMPLATE.format(
            title=APP_TITLE,
            error_html=(
                f'<div class="alert alert-danger">{error}</div>'
                if error
                else ""
            ),
            next_path=next_path,
        )
        return HTMLResponse(content=html, status_code=200)


# ── 登錄頁面內聯 HTML 模板 ─────────────────────────────────
_LOGIN_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>登錄 - {title}</title>
    <link href="https://cdn.bootcdn.net/ajax/libs/bootstrap/5.3.3/css/bootstrap.min.css" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: #0f1117;
            color: #e1e4e8;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .login-card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 40px;
            width: 100%;
            max-width: 400px;
        }}
        .login-card h1 {{
            font-size: 20px;
            font-weight: 600;
            text-align: center;
            margin-bottom: 8px;
        }}
        .login-card h1 i {{
            color: #58a6ff;
            margin-right: 8px;
        }}
        .login-card .subtitle {{
            text-align: center;
            color: #8b949e;
            font-size: 13px;
            margin-bottom: 28px;
        }}
        .form-control {{
            background: #0d1117;
            border-color: #30363d;
            color: #e1e4e8;
            font-size: 14px;
            padding: 10px 14px;
        }}
        .form-control:focus {{
            background: #0d1117;
            border-color: #58a6ff;
            color: #e1e4e8;
            box-shadow: 0 0 0 3px rgba(88,166,255,0.15);
        }}
        .form-label {{
            font-size: 13px;
            color: #8b949e;
            margin-bottom: 6px;
        }}
        .btn-login {{
            width: 100%;
            padding: 10px;
            font-weight: 500;
            background: #238636;
            border-color: #2ea043;
            font-size: 14px;
        }}
        .btn-login:hover {{
            background: #2ea043;
            border-color: #3fb950;
        }}
        .alert {{
            font-size: 13px;
            padding: 10px 14px;
            margin-bottom: 16px;
        }}
    </style>
</head>
<body>
    <div class="login-card">
        <h1><i class="bi bi-shield-lock-fill"></i>{title}</h1>
        <p class="subtitle">請輸入訪問密碼以繼續</p>
        {error_html}
        <form method="post" action="/login">
            <input type="hidden" name="next" value="{next_path}">
            <div class="mb-3">
                <label for="password" class="form-label">訪問密碼</label>
                <input
                    type="password"
                    class="form-control"
                    id="password"
                    name="password"
                    placeholder="請輸入密碼"
                    required
                    autofocus
                >
            </div>
            <button type="submit" class="btn btn-success btn-login">
                <i class="bi bi-box-arrow-in-right"></i> 登錄
            </button>
        </form>
    </div>
</body>
</html>"""
