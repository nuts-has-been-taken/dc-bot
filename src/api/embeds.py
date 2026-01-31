"""Discord Embed Formatter - Format job notifications as Discord embeds."""

from datetime import datetime
from typing import Any

import discord

from .schemas import JobNotificationRequest


# Embed 顏色定義
COLORS = {
    "success": 0x2ECC71,  # 綠色
    "failure": 0xE74C3C,  # 紅色
    "warning": 0xF1C40F,  # 黃色
}

# 狀態標題與圖示
STATUS_INFO = {
    "success": {"title": "任務執行成功", "emoji": "✅"},
    "failure": {"title": "任務執行失敗", "emoji": "❌"},
    "warning": {"title": "任務完成但有警告", "emoji": "⚠️"},
}


def format_duration(seconds: float) -> str:
    """格式化執行時間。"""
    if seconds < 60:
        return f"{seconds:.2f} 秒"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes} 分 {secs:.2f} 秒"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours} 小時 {minutes} 分"


def format_timestamp(iso_timestamp: str) -> str:
    """格式化 ISO 8601 時間戳為易讀格式。"""
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return iso_timestamp


def create_job_notification_embed(payload: JobNotificationRequest) -> discord.Embed:
    """
    建立 Job 通知的 Discord Embed。

    Args:
        payload: Job 通知請求資料

    Returns:
        discord.Embed: 格式化的 Discord Embed
    """
    status_info = STATUS_INFO.get(payload.status, STATUS_INFO["success"])
    color = COLORS.get(payload.status, COLORS["success"])

    embed = discord.Embed(
        title=f"{status_info['emoji']} {status_info['title']}",
        color=color,
    )

    # 基本欄位
    embed.add_field(name="任務名稱", value=f"`{payload.job_name}`", inline=True)
    embed.add_field(
        name="執行時間", value=format_duration(payload.duration_seconds), inline=True
    )

    # 根據狀態添加不同欄位
    if payload.status == "failure" and payload.error_message:
        embed.add_field(
            name="錯誤訊息",
            value=f"```{payload.error_message[:1000]}```",
            inline=False,
        )
    elif payload.status == "success":
        embed.add_field(name="處理筆數", value=str(payload.records_count), inline=True)
    elif payload.status == "warning":
        embed.add_field(name="處理筆數", value=str(payload.records_count), inline=True)
        warning_count = payload.warning_count or len(payload.warnings)
        embed.add_field(name="警告數量", value=str(warning_count), inline=True)

        # 顯示警告內容（最多 5 條）
        if payload.warnings:
            warnings_text = "\n".join(
                f"• {w}" for w in payload.warnings[:5]
            )
            if len(payload.warnings) > 5:
                warnings_text += f"\n... 還有 {len(payload.warnings) - 5} 條警告"
            embed.add_field(name="警告內容", value=warnings_text, inline=False)

    # 額外欄位
    if payload.extra_fields:
        extra_text = "\n".join(
            f"**{k}**: {v}" for k, v in list(payload.extra_fields.items())[:5]
        )
        embed.add_field(name="額外資訊", value=extra_text, inline=False)

    # 完成時間
    embed.set_footer(text=f"完成時間: {format_timestamp(payload.timestamp)}")

    return embed
