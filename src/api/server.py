"""FastAPI Server - API server for receiving external notifications."""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from src.config import Config

from .routes import notifications_router
from .schemas import HealthResponse


def create_app(bot=None) -> FastAPI:
    """
    建立 FastAPI 應用程式。

    Args:
        bot: Discord Bot 實例（可選，可稍後設定）

    Returns:
        FastAPI: 應用程式實例
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """應用程式生命週期管理。"""
        print("FastAPI server starting...")
        yield
        print("FastAPI server shutting down...")

    app = FastAPI(
        title="Discord Bot Notification API",
        description="接收外部系統的通知並轉發到 Discord",
        version="1.0.0",
        lifespan=lifespan,
    )

    # 儲存 bot 實例
    app.state.bot = bot

    # 註冊路由
    app.include_router(notifications_router)

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health_check() -> HealthResponse:
        """健康檢查端點。"""
        bot_instance = app.state.bot
        bot_connected = (
            bot_instance is not None
            and bot_instance.is_ready()
        )
        return HealthResponse(
            status="ok",
            bot_connected=bot_connected,
        )

    return app
