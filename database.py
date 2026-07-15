"""
Работа с базой данных SQLite.
Хранит заявки игроков и их статусы (pending / approved / rejected).
"""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from config import DB_PATH


@dataclass
class Application:
    id: int
    user_id: int
    username: Optional[str]
    full_name: str
    nickname: str
    experience: str
    plans: str
    video_links: str
    status: str
    reject_reason: Optional[str]
    admin_id: Optional[int]
    created_at: str
    decided_at: Optional[str]


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT NOT NULL,
                nickname TEXT NOT NULL,
                experience TEXT NOT NULL,
                plans TEXT NOT NULL,
                video_links TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                reject_reason TEXT,
                admin_id INTEGER,
                created_at TEXT NOT NULL,
                decided_at TEXT
            )
            """
        )
        # Индекс ускоряет проверку "есть ли у игрока уже активная заявка"
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_applications_user_status "
            "ON applications(user_id, status)"
        )


def create_application(
    user_id: int,
    username: Optional[str],
    full_name: str,
    nickname: str,
    experience: str,
    plans: str,
    video_links: str,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO applications
                (user_id, username, full_name, nickname, experience, plans, video_links,
                 status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                user_id,
                username,
                full_name,
                nickname,
                experience,
                plans,
                video_links,
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )
        return cur.lastrowid


def has_pending_application(user_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM applications WHERE user_id = ? AND status = 'pending' LIMIT 1",
            (user_id,),
        ).fetchone()
        return row is not None


def get_application(app_id: int) -> Optional[Application]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM applications WHERE id = ?", (app_id,)
        ).fetchone()
        return Application(**dict(row)) if row else None


def set_status(
    app_id: int,
    status: str,
    admin_id: int,
    reject_reason: Optional[str] = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE applications
            SET status = ?, admin_id = ?, reject_reason = ?, decided_at = ?
            WHERE id = ?
            """,
            (
                status,
                admin_id,
                reject_reason,
                datetime.utcnow().isoformat(timespec="seconds"),
                app_id,
            ),
        )


def list_pending() -> list[Application]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM applications WHERE status = 'pending' ORDER BY id"
        ).fetchall()
        return [Application(**dict(r)) for r in rows]


def list_by_user(user_id: int) -> list[Application]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM applications WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
        return [Application(**dict(r)) for r in rows]
