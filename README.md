# WePush Web

微信公眾號模板消息推送管理面板。

## 功能

- **模板消息管理** — 創建、編輯、刪除微信模板消息模板
- **接收人管理** — 管理關注者 OpenID 列表
- **定時任務** — 基於 Cron 表達式的定時推送
- **數據源集成** — 支持天氣（HKO/OpenWeatherMap/高德）、地圖（高德 POI）自動注入模板變量
- **手動推送** — 即時單次推送
- **推送歷史** — 詳細的推送記錄和狀態追蹤

## 技術棧

| 項目 | 內容 |
|------|------|
| 框架 | FastAPI + Jinja2 |
| 數據庫 | SQLite + SQLAlchemy |
| 定時任務 | APScheduler (AsyncIO) |
| HTTP 客戶端 | httpx |
| 端口 | 8765 |

## 快速開始

```bash
# 1. 克隆
git clone https://github.com/nicklam1994/wepush-web.git
cd wepush-web

# 2. 虛擬環境
python3 -m venv venv
source venv/bin/activate   # Windows: venv\\Scripts\\activate

# 3. 依賴
pip install -r requirements.txt

# 4. 啟動
python main.py
```

打開瀏覽器訪問 http://localhost:8765

## 使用流程

1. **帳號設置** → 填入微信測試號的 AppID / AppSecret
2. **模板管理** → 創建模板消息，填入微信模板 ID 和變量字段
3. **接收人管理** → 添加用戶 OpenID
4. **任務管理** → 設定定時推送（Cron + 數據源）
5. **手動推送** → 即時發送

## 天氣數據源

| 來源 | API Key | 說明 |
|------|---------|------|
| 香港天文台 (HKO) | 不需 | 默認源，限香港地區 |
| OpenWeatherMap | 可選 | 全球覆蓋 |
| 高德地圖 | 可選 | 中國大陸城市 |

## 授權

MIT License
