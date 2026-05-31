"""
WePush Web - 微信公眾號推送管理面板
==================================
A web-based management panel for WeChat official account template message push.

Features:
  - Template message CRUD management
  - Recipient (OpenID) management
  - Cron-based scheduled push tasks
  - Weather/Map API data source integration
  - Manual one-off push
  - Push history with detailed logs

Usage:
  python main.py

Then open http://localhost:8765 in browser.
"""
import logging
import sys
import os

# 確保項目根目錄在 Python 路徑中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from database import init_db, get_db
from scheduler import init_scheduler


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App startup/shutdown."""
    logger.info("=" * 50)
    logger.info("  WePush Web starting up...")
    logger.info("=" * 50)

    # 初始化數據庫
    init_db()
    logger.info("✓ Database initialized")

    # 初始化排程器
    init_scheduler()
    logger.info("✓ Scheduler started")

    yield

    # shutdown
    from scheduler import scheduler
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("✓ Scheduler shut down")


app = FastAPI(
    title="WePush Web",
    description="微信公眾號推送管理面板",
    version="1.0.0",
    lifespan=lifespan,
)

# 靜態文件
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 路由
from routes import router
app.include_router(router)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="WePush Web")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8765, help="监听端口")
    parser.add_argument("--reload", action="store_true", help="自动重载（开发用）")
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════╗
║        WePush Web v1.0              ║
║      微信公眾號推送管理面板          ║
╠══════════════════════════════════════╣
║  🌐 http://localhost:{args.port}           ║
║                                      ║
║  1. 先在「帳號設置」配置微信測試號   ║
║  2. 創建模板消息模板                  ║
║  3. 添加接收人 OpenID                ║
║  4. 設置定時任務或手動推送            ║
╚══════════════════════════════════════╝
""")

    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
