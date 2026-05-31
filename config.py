"""
WePush Web 全局配置
==================
所有配置項都支持從環境變量讀取，提供合理的默認值。
敏感信息（如加密密鑰）首次啟動時自動生成，切勿洩漏。
"""

import os
import secrets
import base64
from pathlib import Path

# ── 項目基礎路徑 ──────────────────────────────────────────
_BASE_DIR = Path(__file__).resolve().parent

# ── 應用標題 & 伺服器配置 ─────────────────────────────────
APP_TITLE = os.getenv("WEPUSH_APP_TITLE", "WePush Web")
APP_HOST = os.getenv("WEPUSH_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("WEPUSH_PORT", "8765"))

# ── 數據目錄 & 數據庫 ─────────────────────────────────────
DATA_DIR = os.getenv("WEPUSH_DATA_DIR", str(_BASE_DIR / "data"))
DB_PATH = os.getenv("WEPUSH_DB_PATH", os.path.join(DATA_DIR, "wepush.db"))

# 確保 data 目錄存在
os.makedirs(DATA_DIR, exist_ok=True)

# ── 分頁默認值 ────────────────────────────────────────────
PER_PAGE = int(os.getenv("WEPUSH_PER_PAGE", "20"))

# ── 加密密鑰 ──────────────────────────────────────────────
# 首次啟動自動生成，切勿洩漏
# 用於加密敏感數據（如微信 appsecret 等）
_ENV_KEY = os.getenv("WEPUSH_ENCRYPTION_KEY", "")
if _ENV_KEY:
    ENCRYPTION_KEY = _ENV_KEY
else:
    # 自動生成 32 字節隨機密鑰並 base64 編碼
    _raw = secrets.token_bytes(32)
    ENCRYPTION_KEY = base64.urlsafe_b64encode(_raw).decode("ascii")
    # 寫入 .env 文件以便持久化（如果 .env 不存在則不寫）
    _env_path = _BASE_DIR / ".env"
    if _env_path.exists():
        _existing = _env_path.read_text(encoding="utf-8")
        if "WEPUSH_ENCRYPTION_KEY" not in _existing:
            with open(_env_path, "a", encoding="utf-8") as f:
                f.write(f"\n# 首次啟動自動生成，切勿洩漏\nWEPUSH_ENCRYPTION_KEY={ENCRYPTION_KEY}\n")

# ── 認證令牌 ──────────────────────────────────────────────
# 設置後，所有非 /static/* 頁面都需要認證；為空則跳過認證（向後兼容）
AUTH_TOKEN = os.getenv("WEPUSH_AUTH_TOKEN", "")

# ── 速率限制 ──────────────────────────────────────────────
RATELIMIT_MAX_REQUESTS = int(os.getenv("WEPUSH_RATELIMIT_MAX", "5"))    # 每窗口最大請求數
RATELIMIT_WINDOW_SECS = int(os.getenv("WEPUSH_RATELIMIT_WINDOW", "60"))  # 時間窗口秒數
