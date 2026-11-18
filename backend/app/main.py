"""FastAPI routes for the Resume_NER prototype."""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .auth import checkpw, current, hashpw, role_required, token
from .config import (
    APP_ENV,
    ENABLE_DEMO_ACCOUNTS,
    MAX_UPLOAD_MB,
    SECRET_KEY,
    UPLOAD_DIR,
)
from .db import conn, init
from .pipeline import jd_skills, norm, parse_resume, read_file, score
from .vector_store import add, search


LOGGER = logging.getLogger(__name__)
DEFAULT_DEVELOPMENT_SECRET = "DEV-ONLY-change-this-secret-before-deployment"
ALLOWED_RESUME_EXTENSIONS = {".pdf", ".docx", ".txt"}

app = FastAPI(
    title="Resume_NER ATS Readiness API",
    version="1.0.0",
    description=(
        "A prototype for resume extraction, skill normalization, and "
        "explainable job-description alignment."
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    role: str


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class JobRequest(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    company: str = Field(min_length=2, max_length=160)
    location: str = Field(default="", max_length=160)
    description: str = Field(min_length=50)
    required_skills: list[str] = Field(default_factory=list)


def _validate_runtime_security() -> None:
    if APP_ENV == "production":
        if SECRET_KEY == DEFAULT_DEVELOPMENT_SECRET or len(SECRET_KEY) < 32:
            raise RuntimeError(
                "Production requires a unique SECRET_KEY with at least 32 characters."
            )
    elif SECRET_KEY == DEFAULT_DEVELOPMENT_SECRET:
        LOGGER.warning(
            "Using the development SECRET_KEY. Set SECRET_KEY before deployment."
        )


def _seed_demo_accounts() -> None:
    """Create optional local demo users only when explicitly configured."""
    accounts = [
        (
            os.getenv("DEMO_RECRUITER_NAME", "Demo Recruiter"),
            os.getenv("DEMO_RECRUITER_EMAIL", "recruiter@example.test").strip().lower(),
            os.getenv("DEMO_RECRUITER_PASSWORD", ""),
            "recruiter",
        ),
        (
            os.getenv("DEMO_APPLICANT_NAME", "Demo Applicant"),
            os.getenv("DEMO_APPLICANT_EMAIL", "applicant@example.test").strip().lower(),
            os.getenv("DEMO_APPLICANT_PASSWORD", ""),
            "applicant",
        ),
    ]
    if any(not password for _, _, password, _ in accounts):
        raise RuntimeError(
            "Demo accounts are enabled, but their passwords are not configured."
        )

    with conn() as connection:
        for name, email, password, role in accounts:
            connection.execute(
                """
                INSERT OR IGNORE INTO users (name, email, password_hash, role)
                VALUES (?, ?, ?, ?)
                """,
                (name, email, hashpw(password), role),
            )


def _job_output(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["required_skills"] = json.loads(result["required_skills"] or "[]")
    return result


def _validate_file_signature(data: bytes, extension: str) -> None:
    if extension == ".pdf" and not data.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid PDF.")
    if extension == ".docx" and not data.startswith(b"PK"):
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid DOCX document.")
    if extension == ".txt" and b"\x00" in data:
        raise HTTPException(status_code=415, detail="The uploaded text file contains binary data.")


@app.on_event("startup")
def startup() -> None:
    init()
    _validate_runtime_security()
    if ENABLE_DEMO_ACCOUNTS:
        _seed_demo_accounts()


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "Resume_NER",
        "features": [
            "hybrid extraction",
            "skill normalization",
            "explainable scoring",
            "public job-description search",
            "ML benchmark evaluation",
        ],
    }


@app.get("/api/model-evaluation")
def model_evaluation(
    user: dict[str, Any] = Depends(role_required("recruiter")),
) -> dict[str, Any]:
    """Return the saved phrase-classifier benchmark report to recruiters."""
    report_path = Path(__file__).resolve().parents[1] / "reports" / "ml_benchmark_evaluation.json"
    if not report_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="The saved ML evaluation report is missing.",
        )

    try:
        with report_path.open("r", encoding="utf-8") as report_file:
            return json.load(report_file)
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.exception("Could not read the saved ML evaluation report.")
        raise HTTPException(
            status_code=500,
            detail="The ML evaluation report could not be read.",
        ) from exc


@app.post("/api/auth/register")
def register(body: RegisterRequest) -> dict[str, Any]:
    role = body.role.strip().lower()
    email = body.email.strip().lower()
    name = body.name.strip()

    if role not in {"recruiter", "applicant"}:
        raise HTTPException(
            status_code=400,
            detail="Role must be recruiter or applicant.",
        )
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")

    try:
        with conn() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (name, email, password_hash, role)
                VALUES (?, ?, ?, ?)
                """,
                (name, email, hashpw(body.password), role),
            )
            user = {
                "id": cursor.lastrowid,
                "name": name,
                "email": email,
                "role": role,
            }
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="An account with this email address already exists.",
        ) from exc

    return {
        "access_token": token(user),
        "token_type": "bearer",
        "user": user,
    }


@app.post("/api/auth/login")
def login(body: LoginRequest) -> dict[str, Any]:
    email = body.email.strip().lower()
    with conn() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,),
        ).fetchone()

    if row is None or not checkpw(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    user = {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
    }
    return {
        "access_token": token(user),
        "token_type": "bearer",
        "user": user,
    }


@app.get("/api/me")
def me(user: dict[str, Any] = Depends(current)) -> dict[str, Any]:
    return user


@app.post("/api/jobs")
def create_job(
    body: JobRequest,
    user: dict[str, Any] = Depends(role_required("recruiter")),
) -> dict[str, Any]:
    skills = jd_skills(body.description, body.required_skills)
    with conn() as connection:
        cursor = connection.execute(
            """
            INSERT INTO jobs (
                recruiter_id, title, company, location, description, required_skills
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                body.title.strip(),
                body.company.strip(),
                body.location.strip(),
                norm(body.description),
                json.dumps(skills),
            ),
        )
        row = connection.execute(
            """
            SELECT jobs.*, users.name AS recruiter_name
            FROM jobs
            JOIN users ON users.id = jobs.recruiter_id
            WHERE jobs.id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

    add(
        f"job-{row['id']}",
        body.description,
        {
            "kind": "job",
            "job_id": row["id"],
            "recruiter_id": user["id"],
            "title": body.title.strip(),
        },
    )
    return _job_output(row)


@app.get("/api/jobs")
def jobs(user: dict[str, Any] = Depends(current)) -> list[dict[str, Any]]:
    with conn() as connection:
        rows = connection.execute(
            """
            SELECT jobs.*, users.name AS recruiter_name
            FROM jobs
            JOIN users ON users.id = jobs.recruiter_id
            ORDER BY jobs.created_at DESC
            """
        ).fetchall()
    return [_job_output(row) for row in rows]


@app.post("/api/applications")
async def upload_resume(
    job_id: int,
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(role_required("applicant")),
) -> dict[str, Any]:
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_RESUME_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Upload a PDF, DOCX, or TXT file. Convert legacy DOC files to DOCX.",
        )

    # Read one byte over the configured limit so oversized files are rejected
    # without buffering an unbounded upload into memory.
    data = await file.read(MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"The file exceeds the {MAX_UPLOAD_MB} MB upload limit.",
        )
    _validate_file_signature(data, extension)

    with conn() as connection:
        job = connection.execute(
            "SELECT id FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    if job is None:
        raise HTTPException(status_code=404, detail="Job description not found.")

    original_name = Path(file.filename or "resume").name
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", original_name)[:120]
    stored_path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{safe_name}"
    stored_path.write_bytes(data)

    try:
        extracted_text = norm(read_file(stored_path))
    except Exception as exc:
        stored_path.unlink(missing_ok=True)
        LOGGER.info("Resume extraction failed for upload %s: %s", safe_name, type(exc).__name__)
        raise HTTPException(
            status_code=422,
            detail="Could not extract text. Check that the file is readable and not password-protected.",
        ) from exc

    if len(extracted_text.strip()) < 20:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail="No usable text was extracted. Scanned PDFs need OCR before upload.",
        )

    parsed = parse_resume(extracted_text)
    try:
        with conn() as connection:
            cursor = connection.execute(
                """
                INSERT INTO applications (
                    applicant_id, job_id, filename, file_path,
                    extracted_text, parsed_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, 'uploaded')
                """,
                (
                    user["id"],
                    job_id,
                    safe_name,
                    str(stored_path),
                    extracted_text,
                    json.dumps(parsed),
                ),
            )
            application_id = cursor.lastrowid
    except sqlite3.IntegrityError as exc:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=409,
            detail="You have already uploaded a resume for this job.",
        ) from exc

    # Do not add resume content to the shared retrieval index. Resume data stays
    # with its application record and is exposed only through role-scoped routes.
    return {
        "id": application_id,
        "job_id": job_id,
        "filename": safe_name,
        "status": "uploaded",
        "parsed_preview": {
            "skills": parsed["skills"],
            "email_found": bool(parsed["emails"]),
            "parsing_confidence": parsed["parsing_confidence"],
        },
    }


@app.get("/api/applications")
def applications(user: dict[str, Any] = Depends(current)) -> list[dict[str, Any]]:
    with conn() as connection:
        if user["role"] == "recruiter":
            rows = connection.execute(
                """
                SELECT
                    applications.id, applications.job_id, applications.applicant_id,
                    applications.filename, applications.status, applications.created_at,
                    applications.score_json, users.name AS applicant_name,
                    users.email AS applicant_email, jobs.title AS job_title,
                    jobs.company
                FROM applications
                JOIN users ON users.id = applications.applicant_id
                JOIN jobs ON jobs.id = applications.job_id
                WHERE jobs.recruiter_id = ?
                ORDER BY applications.created_at DESC
                """,
                (user["id"],),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT
                    applications.id, applications.job_id, applications.applicant_id,
                    applications.filename, applications.status, applications.created_at,
                    applications.score_json, jobs.title AS job_title, jobs.company
                FROM applications
                JOIN jobs ON jobs.id = applications.job_id
                WHERE applications.applicant_id = ?
                ORDER BY applications.created_at DESC
                """,
                (user["id"],),
            ).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["result"] = json.loads(item.pop("score_json") or "{}")
        result.append(item)
    return result


@app.post("/api/applications/{application_id}/analyze")
def analyze(
    application_id: int,
    user: dict[str, Any] = Depends(role_required("recruiter")),
) -> dict[str, Any]:
    with conn() as connection:
        row = connection.execute(
            """
            SELECT
                applications.*, jobs.description AS job_description,
                jobs.required_skills, jobs.recruiter_id, jobs.title AS job_title,
                jobs.company
            FROM applications
            JOIN jobs ON jobs.id = applications.job_id
            WHERE applications.id = ?
            """,
            (application_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    if row["recruiter_id"] != user["id"]:
        raise HTTPException(
            status_code=403,
            detail="You can analyze applications only for your own job descriptions.",
        )

    parsed = json.loads(row["parsed_json"] or "{}")
    result = score(
        parsed,
        row["extracted_text"],
        row["job_description"],
        json.loads(row["required_skills"] or "[]"),
    )
    with conn() as connection:
        connection.execute(
            "UPDATE applications SET score_json = ?, status = 'analyzed' WHERE id = ?",
            (json.dumps(result), application_id),
        )

    return {
        "application_id": application_id,
        "parsed": parsed,
        "result": result,
        "job_title": row["job_title"],
        "company": row["company"],
        "filename": row["filename"],
    }


@app.get("/api/applications/{application_id}")
def application_detail(
    application_id: int,
    user: dict[str, Any] = Depends(current),
) -> dict[str, Any]:
    with conn() as connection:
        row = connection.execute(
            """
            SELECT
                applications.*, jobs.title AS job_title, jobs.company,
                jobs.recruiter_id, users.name AS applicant_name,
                users.email AS applicant_email
            FROM applications
            JOIN jobs ON jobs.id = applications.job_id
            JOIN users ON users.id = applications.applicant_id
            WHERE applications.id = ?
            """,
            (application_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Application not found.")

    recruiter_cannot_view = (
        user["role"] == "recruiter" and row["recruiter_id"] != user["id"]
    )
    applicant_cannot_view = (
        user["role"] == "applicant" and row["applicant_id"] != user["id"]
    )
    if recruiter_cannot_view or applicant_cannot_view:
        raise HTTPException(status_code=403, detail="Not authorized for this application.")

    result = dict(row)
    result["parsed"] = json.loads(result.pop("parsed_json") or "{}")
    result["result"] = json.loads(result.pop("score_json") or "{}")
    result.pop("file_path", None)
    result.pop("extracted_text", None)
    return result


@app.get("/api/search")
def vector_search(
    query: str = Query(min_length=2, alias="q"),
    user: dict[str, Any] = Depends(current),
) -> dict[str, Any]:
    """Search publicly listed job descriptions, never resumes or applications."""
    if len(query.strip()) < 2:
        raise HTTPException(
            status_code=400,
            detail="Search query must contain at least 2 characters.",
        )
    return {"results": search(query, 5)}
