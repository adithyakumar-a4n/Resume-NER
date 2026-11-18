"""Small regression tests for skill extraction and job requirement handling."""

from app.pipeline import _find_skill_terms, jd_skills, norm


def test_normalization_handles_newlines_and_long_dashes():
    assert norm("FastAPI  —  Python\r\nSQL") == "FastAPI - Python\nSQL"


def test_explicit_negation_does_not_count_as_skill_evidence():
    skills = _find_skill_terms("I have Python experience, but I have not used SQL.")
    assert "python" in skills
    assert "sql" not in skills


def test_explicit_required_skills_override_contextual_job_keywords():
    skills = jd_skills(
        "Role requires Python and SQL. Exposure to Docker is preferred.",
        ["Python", "Postgres"],
    )
    assert skills == ["postgresql", "python"]
