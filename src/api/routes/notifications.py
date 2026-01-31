"""Notifications API Routes - Handle job notification requests."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config import Config

from ..embeds import create_job_notification_embed
from ..schemas import JobNotificationRequest, JobNotificationResponse

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])
security = HTTPBearer()


def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """驗證 API Key。"""
    api_config = Config.get_api_config()
    expected_key = api_config.get("api_key")

    if not expected_key:
        # 如果沒有設定 API Key，跳過驗證（開發環境）
        return credentials.credentials

    if credentials.credentials != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


@router.post(
    "/job-result",
    response_model=JobNotificationResponse,
    summary="接收 Job 執行結果通知",
    description="接收來自排程系統的 Job 執行結果，並轉發到指定的 Discord 頻道",
)
async def receive_job_notification(
    request: Request,
    payload: JobNotificationRequest,
    api_key: str = Depends(verify_api_key),
) -> JobNotificationResponse:
    """
    接收 Job 執行結果通知並發送到 Discord。

    - **job_name**: 任務名稱
    - **status**: 執行狀態 (success/failure/warning)
    - **channel_id**: Discord 頻道 ID（選填）
    - **timestamp**: 完成時間
    - **duration_seconds**: 執行時間
    - **records_count**: 處理筆數
    - **error_message**: 錯誤訊息（失敗時）
    - **warnings**: 警告列表
    - **extra_fields**: 額外欄位
    """
    # 從 app state 取得 bot 實例
    bot = request.app.state.bot

    if not bot:
        return JobNotificationResponse(
            success=False,
            error="Discord Bot not initialized",
        )

    if not bot.is_ready():
        return JobNotificationResponse(
            success=False,
            error="Discord Bot not connected",
        )

    # 決定目標頻道
    api_config = Config.get_api_config()
    channel_id = payload.channel_id or api_config.get("default_channel_id")

    if not channel_id:
        return JobNotificationResponse(
            success=False,
            error="No channel_id provided and no default channel configured",
        )

    try:
        channel_id_int = int(channel_id)
    except ValueError:
        return JobNotificationResponse(
            success=False,
            error=f"Invalid channel_id format: {channel_id}",
        )

    # 取得頻道
    channel = bot.get_channel(channel_id_int)

    if not channel:
        # 嘗試 fetch（可能是私人頻道或未快取）
        try:
            channel = await bot.fetch_channel(channel_id_int)
        except Exception as e:
            return JobNotificationResponse(
                success=False,
                error=f"Channel {channel_id} not found or bot has no access: {str(e)}",
            )

    # 建立 Embed 訊息
    embed = create_job_notification_embed(payload)

    # 發送訊息
    try:
        message = await channel.send(embed=embed)
        return JobNotificationResponse(
            success=True,
            message_id=str(message.id),
        )
    except Exception as e:
        return JobNotificationResponse(
            success=False,
            error=f"Failed to send message: {str(e)}",
        )
