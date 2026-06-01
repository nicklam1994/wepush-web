"""SQLAlchemy models for WePush Web."""
import os
import base64
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, Float
from cryptography.fernet import Fernet
from database import Base

# ---------------------------------------------------------------------------
# Encryption helpers for appsecret
# ---------------------------------------------------------------------------
_ENCRYPTION_KEY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", ".encryption_key"
)


def _get_fernet() -> Fernet:
    """Return a Fernet instance, creating the key file if it does not exist."""
    os.makedirs(os.path.dirname(_ENCRYPTION_KEY_PATH), exist_ok=True)

    if os.path.exists(_ENCRYPTION_KEY_PATH):
        with open(_ENCRYPTION_KEY_PATH, "rb") as f:
            key = f.read()
    else:
        key = Fernet.generate_key()
        with open(_ENCRYPTION_KEY_PATH, "wb") as f:
            f.write(key)

    return Fernet(key)


def encrypt_secret(text: str) -> str:
    """Encrypt a plain-text secret.  Returns a base64-encoded token string."""
    if not text:
        return text
    f = _get_fernet()
    return f.encrypt(text.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    """Decrypt a previously-encrypted secret.

    Falls back to returning the input as plain text when decryption fails,
    so existing (unencrypted) data continues to work.
    """
    if not token:
        return token
    try:
        f = _get_fernet()
        return f.decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception:
        # Backward compatibility: stored value may be unencrypted
        return token


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class WechatAccount(Base):
    """微信测试号/正式号配置"""
    __tablename__ = "wechat_accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, default="默认账号")
    appid = Column(String(200), nullable=False)
    appsecret = Column(String(500), nullable=False)  # stored encrypted
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    @property
    def appsecret_plain(self) -> str:
        """Returns the decrypted appsecret."""
        return decrypt_secret(self.appsecret)

    @appsecret_plain.setter
    def appsecret_plain(self, value: str) -> None:
        """Stores the encrypted appsecret in the column."""
        self.appsecret = encrypt_secret(value)


class Template(Base):
    """模板消息模板"""
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, comment="模板别名/备注名")
    template_id = Column(String(200), nullable=False, comment="微信模板ID")
    url = Column(String(500), default="", comment="点击跳转链接")
    ma_appid = Column(String(200), default="", comment="跳转小程序appid")
    ma_page_path = Column(String(500), default="", comment="跳转小程序页面路径")
    # JSON array of {name, value, color}
    data_fields = Column(JSON, default=list, comment="模板数据字段定义")
    remark = Column(Text, default="", comment="备注说明")
    is_deleted = Column(Boolean, default=False, comment="软删除标记")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Recipient(Base):
    """接收人（关注者OpenID）"""
    __tablename__ = "recipients"

    id = Column(Integer, primary_key=True, index=True)
    nickname = Column(String(100), default="", comment="备注名")
    openid = Column(String(200), nullable=False, unique=True, comment="微信OpenID")
    note = Column(String(500), default="", comment="备注")
    created_at = Column(DateTime, default=datetime.now)


class Task(Base):
    """定時推送任務"""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, comment="任务名称")
    template_id = Column(Integer, nullable=False, comment="关联模板ID")
    # JSON array of recipient IDs or "all"
    recipient_ids = Column(JSON, default=list, comment="接收人ID列表")
    cron_expr = Column(String(100), nullable=False, comment="cron 表达式")
    # data_source: "manual" | "weather" | "map" | "weather_map"
    data_source = Column(String(50), default="manual", comment="数据源类型")
    # JSON config for data sources
    data_config = Column(JSON, default=dict, comment="数据源配置")
    # Variable mapping: {"weather_temp":"{{temp}}", ...}
    var_mapping = Column(JSON, default=dict, comment="变量映射")
    is_active = Column(Boolean, default=True, comment="是否启用")
    last_run = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class PushHistory(Base):
    """推送歷史記錄"""
    __tablename__ = "push_history"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, nullable=True, comment="关联任务ID(0=手动)")
    task_name = Column(String(200), default="手动推送", comment="任务名称")
    template_name = Column(String(200), default="", comment="模板名称")
    trigger_type = Column(String(20), default="manual", comment="触发方式: manual/cron")
    total_count = Column(Integer, default=0, comment="目标人数")
    success_count = Column(Integer, default=0, comment="成功数")
    fail_count = Column(Integer, default=0, comment="失败数")
    # JSON array of {openid, status, error}
    details = Column(JSON, default=list, comment="推送详情")
    status = Column(String(20), default="pending", comment="pending/success/partial/fail")
    created_at = Column(DateTime, default=datetime.now)


class DateEvent(Base):
    """自定義日期事件（倒計時/正計時）"""
    __tablename__ = "date_events"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, comment="事件名稱")
    target_date = Column(String(10), nullable=False, comment="目標日期 YYYY-MM-DD")
    direction = Column(String(20), default="countdown", comment="countdown/countup")
    created_at = Column(DateTime, default=datetime.now)
