"""Regression tests for search-index data isolation."""

from __future__ import annotations

import json
import sqlite3

import pytest

from app import vector_store


def _write_legacy_rows(database_path):
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE documents (id TEXT PRIMARY KEY, body TEXT, metadata TEXT)"
        )
        connection.executemany(
            "INSERT INTO documents VALUES (?, ?, ?)",
            [
                (
                    "old-resume-1",
                    "Confidential candidate medical history and Python experience",
                    json.dumps({"kind": "resume", "application_id": "1"}),
                ),
                (
                    "job-1",
                    "Python backend engineer role with FastAPI and SQL",
                    json.dumps({"kind": "job", "job_id": "1"}),
                ),
            ],
        )


def test_add_rejects_resume_documents(tmp_path, monkeypatch):
    monkeypatch.setattr(vector_store, "FALLBACK_DATABASE", tmp_path / "search.db")

    with pytest.raises(ValueError, match="Only public job descriptions"):
        vector_store.add(
            "application-7",
            "Private candidate resume content",
            {"kind": "resume", "application_id": 7},
        )


def test_search_excludes_legacy_resume_rows(tmp_path, monkeypatch):
    database_path = tmp_path / "search.db"
    monkeypatch.setattr(vector_store, "FALLBACK_DATABASE", database_path)
    _write_legacy_rows(database_path)

    results = vector_store._search_sqlite("Python backend engineer", 5)

    assert results
    assert all(item["metadata"].get("kind") == "job" for item in results)
    assert all("medical history" not in item["text"] for item in results)


def test_search_returns_empty_when_only_resumes_are_indexed(tmp_path, monkeypatch):
    database_path = tmp_path / "search.db"
    monkeypatch.setattr(vector_store, "FALLBACK_DATABASE", database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE documents (id TEXT PRIMARY KEY, body TEXT, metadata TEXT)"
        )
        connection.execute(
            "INSERT INTO documents VALUES (?, ?, ?)",
            (
                "old-resume-2",
                "Python and SQL experience",
                json.dumps({"kind": "resume", "application_id": "2"}),
            ),
        )

    assert vector_store._search_sqlite("Python", 5) == []
