"""SQLite-backed session index. Conversation content lives in markdown files."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import aiosqlite


Mode = Literal["chat", "work", "dm"]


@dataclass(frozen=True)
class Session:
    discord_session_id: str
    user_id: str
    mode: Mode
    claude_session_id: str | None
    created_at: datetime
    last_active_at: datetime
    metadata: dict


class SessionStore:
    """Thin async wrapper over a single-table SQLite index."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS sessions (
        discord_session_id TEXT PRIMARY KEY,
        user_id            TEXT NOT NULL,
        mode               TEXT NOT NULL,
        claude_session_id  TEXT,
        created_at         TEXT NOT NULL,
        last_active_at     TEXT NOT NULL,
        metadata_json      TEXT NOT NULL
    );
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    async def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(self.SCHEMA)
            await db.commit()

    async def create(
        self,
        *,
        discord_session_id: str,
        user_id: str,
        mode: Mode,
        metadata: dict,
    ) -> Session:
        now = datetime.now(UTC)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO sessions "
                "(discord_session_id, user_id, mode, claude_session_id, "
                "created_at, last_active_at, metadata_json) "
                "VALUES (?, ?, ?, NULL, ?, ?, ?)",
                (
                    discord_session_id,
                    user_id,
                    mode,
                    now.isoformat(),
                    now.isoformat(),
                    json.dumps(metadata),
                ),
            )
            await db.commit()
        return Session(
            discord_session_id=discord_session_id,
            user_id=user_id,
            mode=mode,
            claude_session_id=None,
            created_at=now,
            last_active_at=now,
            metadata=metadata,
        )

    async def get(self, discord_session_id: str) -> Session | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM sessions WHERE discord_session_id = ?",
                (discord_session_id,),
            ) as cur:
                row = await cur.fetchone()
        if row is None:
            return None
        return Session(
            discord_session_id=row["discord_session_id"],
            user_id=row["user_id"],
            mode=row["mode"],
            claude_session_id=row["claude_session_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            last_active_at=datetime.fromisoformat(row["last_active_at"]),
            metadata=json.loads(row["metadata_json"]),
        )

    async def update_claude_session(
        self, discord_session_id: str, claude_session_id: str
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE sessions SET claude_session_id = ?, last_active_at = ? "
                "WHERE discord_session_id = ?",
                (
                    claude_session_id,
                    datetime.now(UTC).isoformat(),
                    discord_session_id,
                ),
            )
            await db.commit()

    async def touch(self, discord_session_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE sessions SET last_active_at = ? "
                "WHERE discord_session_id = ?",
                (datetime.now(UTC).isoformat(), discord_session_id),
            )
            await db.commit()

    async def delete(self, discord_session_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM sessions WHERE discord_session_id = ?",
                (discord_session_id,),
            )
            await db.commit()
