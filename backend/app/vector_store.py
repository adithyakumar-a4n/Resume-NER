"""Small local search index for public job descriptions only.

Resume text is deliberately not indexed here. Application documents can contain
personal data and must never be returned by a cross-account search endpoint.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .config import DATA_DIR


FALLBACK_DATABASE = DATA_DIR / "vector_fallback.db"
COLLECTION_NAME = "resume_ner_documents"


def add(document_id: str, text: str, metadata: dict[str, Any]) -> str:
    """Add a document to the local index.

    Only records explicitly tagged as ``kind='job'`` are accepted. This guard
    protects the index even if a future caller accidentally passes resume data.
    """
    if metadata.get("kind") != "job":
        raise ValueError("Only public job descriptions may be indexed.")

    safe_metadata = {key: str(value) for key, value in metadata.items()}
    document = text[:20_000]

    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(DATA_DIR / "chroma"))
        collection = client.get_or_create_collection(COLLECTION_NAME)
        collection.upsert(
            ids=[str(document_id)],
            documents=[document],
            metadatas=[safe_metadata],
        )
        return "chromadb"
    except ImportError:
        return _add_sqlite(document_id, document, safe_metadata)
    except Exception:
        # The lightweight fallback keeps local development usable when ChromaDB
        # is unavailable or its optional native runtime cannot be initialized.
        return _add_sqlite(document_id, document, safe_metadata)


def _add_sqlite(
    document_id: str,
    document: str,
    metadata: dict[str, str],
) -> str:
    connection = sqlite3.connect(FALLBACK_DATABASE)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                body TEXT NOT NULL,
                metadata TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT OR REPLACE INTO documents (id, body, metadata) VALUES (?, ?, ?)",
            (str(document_id), document, json.dumps(metadata)),
        )
        connection.commit()
    finally:
        connection.close()
    return "sqlite-fallback"


def search(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search job descriptions only; never return resume/application records."""
    query = query.strip()
    if not query:
        return []

    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(DATA_DIR / "chroma"))
        collection = client.get_or_create_collection(COLLECTION_NAME)
        if collection.count() == 0:
            return []

        result = collection.query(
            query_texts=[query],
            n_results=min(limit, collection.count()),
            where={"kind": "job"},
        )
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        return [
            {"id": item_id, "text": document[:500], "metadata": metadata or {}}
            for item_id, document, metadata in zip(ids, documents, metadatas)
        ]
    except ImportError:
        return _search_sqlite(query, limit)
    except Exception:
        return _search_sqlite(query, limit)


def _search_sqlite(query: str, limit: int) -> list[dict[str, Any]]:
    if not FALLBACK_DATABASE.exists():
        return []

    connection = sqlite3.connect(FALLBACK_DATABASE)
    try:
        rows = connection.execute(
            "SELECT id, body, metadata FROM documents"
        ).fetchall()
    finally:
        connection.close()

    # Filter before vectorization so legacy resume rows in an existing index are
    # excluded from all search results.
    job_rows = []
    for document_id, body, raw_metadata in rows:
        try:
            metadata = json.loads(raw_metadata)
        except (TypeError, json.JSONDecodeError):
            continue
        if metadata.get("kind") == "job":
            job_rows.append((document_id, body, metadata))

    if not job_rows:
        return []

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        matrix = TfidfVectorizer(stop_words="english").fit_transform(
            [query] + [row[1] for row in job_rows]
        )
        similarities = cosine_similarity(matrix[0:1], matrix[1:]).ravel()
    except (ValueError, TypeError):
        return []

    ranked = similarities.argsort()[::-1][: max(1, limit)]
    return [
        {
            "id": job_rows[index][0],
            "text": job_rows[index][1][:500],
            "metadata": job_rows[index][2],
            "similarity": float(similarities[index]),
        }
        for index in ranked
    ]
