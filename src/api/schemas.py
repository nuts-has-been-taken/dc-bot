"""API Schemas - Pydantic models for request/response validation."""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class JobNotificationRequest(BaseModel):
    """Job 執行結果通知請求。"""

    job_name: str = Field(..., description="任務名稱")
    status: Literal["success", "failure", "warning"] = Field(
        ..., description="執行狀態"
    )
    channel_id: Optional[str] = Field(
        None, description="Discord 頻道 ID（選填，使用預設頻道）"
    )
    timestamp: str = Field(..., description="完成時間 (ISO 8601 格式)")
    duration_seconds: float = Field(..., description="執行時間（秒）")
    records_count: int = Field(default=0, description="處理筆數")
    error_message: Optional[str] = Field(None, description="錯誤訊息")
    warnings: list[str] = Field(default_factory=list, description="警告訊息列表")
    warning_count: int = Field(default=0, description="警告數量")
    extra_fields: dict[str, Any] = Field(
        default_factory=dict, description="額外欄位"
    )


class JobNotificationResponse(BaseModel):
    """Job 通知回應。"""

    success: bool = Field(..., description="是否發送成功")
    message_id: Optional[str] = Field(None, description="Discord 訊息 ID")
    error: Optional[str] = Field(None, description="錯誤訊息")


class HealthResponse(BaseModel):
    """健康檢查回應。"""

    status: str = Field(default="ok")
    bot_connected: bool = Field(..., description="Discord Bot 是否已連接")
