"""Pydantic validation schemas for WePush Web forms."""
from typing import Optional
from pydantic import BaseModel, Field


class AccountForm(BaseModel):
    """WeChat account configuration form."""
    name: str = Field(default="默认账号", min_length=1, max_length=100)
    appid: str = Field(..., min_length=1, max_length=200)
    appsecret: str = Field(..., min_length=1, max_length=200)


class TemplateForm(BaseModel):
    """Template message form."""
    name: str = Field(..., min_length=1, max_length=200)
    template_id: str = Field(..., min_length=1, max_length=200)
    url: str = Field(default="", max_length=500)
    ma_appid: str = Field(default="", max_length=200)
    ma_page_path: str = Field(default="", max_length=500)
    data_fields: str = Field(default="[]")
    remark: str = Field(default="", max_length=5000)


class RecipientForm(BaseModel):
    """Recipient form."""
    openid: str = Field(..., min_length=1, max_length=200)
    nickname: str = Field(default="", max_length=100)
    note: str = Field(default="", max_length=500)


class TaskForm(BaseModel):
    """Scheduled task form."""
    name: str = Field(..., min_length=1, max_length=200)
    template_id: int = Field(...)
    recipient_ids: str = Field(default="[]")
    cron_expr: str = Field(default="0 8 * * *", max_length=100)
    data_source: str = Field(default="manual", max_length=50)
    data_config: str = Field(default="{}")
    var_mapping: str = Field(default="{}")
    is_active: bool = Field(default=True)


class PushForm(BaseModel):
    """Manual push form."""
    template_id: int = Field(...)
    recipient_ids: str = Field(default="[]")
    var_values: str = Field(default="{}")
