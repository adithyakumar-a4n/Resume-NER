"""SQLite connection handling and schema initialization."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import DATABASE_PATH


@contextmanager
def conn() -> Iterator[sqlite3.Connection]:
    """Open a database connection and always commit or roll back, then close it."""
    connection = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init() -> None:
    """Create application tables when the database is first initialized."""
    with conn() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY,
                recruiter_id INTEGER NOT NULL REFERENCES users(id),
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT DEFAULT '',
                description TEXT NOT NULL,
                required_skills TEXT NOT NULL DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY,
                applicant_id INTEGER NOT NULL REFERENCES users(id),
                job_id INTEGER NOT NULL REFERENCES jobs(id),
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                extracted_text TEXT DEFAULT '',
                parsed_json TEXT DEFAULT '{}',
                score_json TEXT DEFAULT '{}',
                status TEXT DEFAULT 'uploaded',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(applicant_id, job_id)
            );
            """
        )
