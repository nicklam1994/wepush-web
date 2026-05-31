"""SQLAlchemy models for WePush Web."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, Float
from database import Base


class WechatAccount(Base):
    """微信测试号/正式号配置"""
    __tablename__ = "wechat_accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, default="默认账号")
    appid = Column(String(200), nullable=False)
    appsecret = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Template(Base):
    """模板消息模板"""
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, comment="模板别名/备注名")
    template_id = Column(String(200), nullable=False, comment="微信模板ID")
    url = Column(String(500), default="", comment="点击跳转链接")
    ma_appid = Column(String(200), default="", comment="跳转小程序appid")
    ma_page_path = Column(String(500), default="", comment="跳转小程序页面路径")
    data_fields = Column(JSON, default=list, comment="模板数据字段定义")
    remark = Column(Text, default="", comment="备注说明")
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
    recipient_ids = Column(JSON, default=list, comment="接收人ID列表")
    cron_expr = Column(String(100), nullable=False, comment="cron 表达式")
    data_source = Column(String(50), default="manual", comment="数据源类型")
    data_config = Column(JSON, default=dict, comment="数据源配置")
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
    details = Column(JSON, default=list, comment="推送详情")
    status = Column(String(20), default="pending", comment="pending/success/partial/fail")
    created_at = Column(DateTime, default=datetime.now)
