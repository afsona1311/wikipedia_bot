from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any

LOGGER = logging.getLogger(__name__)
DB_NAME = "wiki_bot.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def _column_exists(cur: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
    cur.execute(f"PRAGMA table_info({table_name})")
    return any(row["name"] == column_name for row in cur.fetchall())


def _ensure_column(
    cur: sqlite3.Cursor,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    if not _column_exists(cur, table_name, column_name):
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def init_db() -> None:
    """Ma'lumotlar bazasini yaratish va kerakli ustunlarni tayyorlash."""
    with _connect() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                full_name TEXT,
                username TEXT,
                first_seen TIMESTAMP,
                last_active TIMESTAMP,
                preferred_language TEXT
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                search_query TEXT,
                wiki_title TEXT,
                wiki_url TEXT,
                ai_summary TEXT,
                search_date TIMESTAMP,
                search_language TEXT
            )
            """
        )

        _ensure_column(cur, "users", "preferred_language", "TEXT")
        _ensure_column(cur, "searches", "search_language", "TEXT")

        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_searches_telegram_id ON searches(telegram_id)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_searches_search_date ON searches(search_date)"
        )

    LOGGER.info("Ma'lumotlar bazasi tayyor.")


def save_user(user, preferred_language: str | None = None) -> None:
    """Foydalanuvchini saqlash yoki yangilash."""
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    now = datetime.now()

    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (
                telegram_id,
                full_name,
                username,
                first_seen,
                last_active,
                preferred_language
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                full_name = excluded.full_name,
                username = excluded.username,
                last_active = excluded.last_active,
                preferred_language = COALESCE(excluded.preferred_language, users.preferred_language)
            """,
            (user.id, full_name, user.username, now, now, preferred_language),
        )


def update_user_language(telegram_id: int, language: str) -> None:
    """Foydalanuvchining tanlangan tilini yangilash."""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET preferred_language = ?, last_active = ? WHERE telegram_id = ?",
            (language, datetime.now(), telegram_id),
        )


def get_user_language(telegram_id: int) -> str | None:
    """Foydalanuvchining saqlangan tilini olish."""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT preferred_language FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = cur.fetchone()

    return str(row["preferred_language"]) if row and row["preferred_language"] else None


def save_search(
    telegram_id: int,
    search_query: str,
    wiki_title: str,
    wiki_url: str,
    ai_summary: str = "",
    search_language: str | None = None,
) -> None:
    """Qidiruvni saqlash."""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO searches (
                telegram_id,
                search_query,
                wiki_title,
                wiki_url,
                ai_summary,
                search_date,
                search_language
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                telegram_id,
                search_query,
                wiki_title,
                wiki_url,
                ai_summary,
                datetime.now(),
                search_language,
            ),
        )


def get_user_stats(telegram_id: int) -> int:
    """Foydalanuvchi statistikasini olish."""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS count FROM searches WHERE telegram_id = ?", (telegram_id,))
        row = cur.fetchone()

    return int(row["count"]) if row else 0


def get_user_history(telegram_id: int, limit: int = 10) -> list[dict[str, Any]]:
    """Foydalanuvchining oxirgi qidiruvlarini olish."""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                search_query,
                wiki_title,
                wiki_url,
                search_date,
                search_language
            FROM searches
            WHERE telegram_id = ?
            ORDER BY search_date DESC
            LIMIT ?
            """,
            (telegram_id, limit),
        )
        rows = cur.fetchall()

    return [
        {
            "query": row["search_query"],
            "title": row["wiki_title"],
            "url": row["wiki_url"],
            "search_date": row["search_date"],
            "language": row["search_language"],
        }
        for row in rows
    ]
