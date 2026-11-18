"""Explainable rule-based, ML-based, and hybrid resume-to-JD analysis."""
import csv
import re
from functools import lru_cache
from pathlib import Path

from pypdf import PdfReader
from docx import Document
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import Pipeline


ALIASES = {
    "python": ["python3"], "javascript": ["js", "ecmascript"], "typescript": ["ts"],
    "react": ["reactjs", "react.js"], "node.js": ["nodejs", "node"], "fastapi": ["fast api"],
    "machine learning": ["ml"], "deep learning": ["dl"], "natural language processing": ["nlp"],
    "large language models": ["llm", "llms"], "sql": ["structured query language"],
    "postgresql": ["postgres", "psql"], "amazon web services": ["aws"],
    "google cloud": ["gcp", "google cloud platform"], "scikit-learn": ["sklearn"],
    "pytorch": ["torch"], "tensorflow": ["tf"], "continuous integration/continuous delivery": ["ci/cd", "cicd"],
    "rest api": ["restful api", "rest apis", "restful apis", "representational state transfer"], "api": ["application programming interface", "application programming interfaces"],
    "data structures and algorithms": ["dsa"], "retrieval augmented generation": ["rag"],
    "vector database": ["vector db", "vectordb"], "kubernetes": ["k8s"],
    "natural language understanding": ["nlu"], "named entity recognition": ["ner"],
    "information retrieval": ["ir"], "pandas": ["python pandas"], "numpy": ["np"],
    "computer vision": ["cv"], "power bi": ["powerbi"], "communication": ["communication skills"],
    "project management": ["project coordination"], "object-oriented programming": ["oop", "object oriented programming"],
    "git": ["git version control"], "github": ["git hub"], "http": ["https protocol"],
    "json": ["javascript object notation"], "flask": [], "django": [], "pytest": [], "docker": [],
    "sqlite": [], "mysql": [], "exception handling": [], "problem solving": ["problem-solving"],
    "relational databases": ["relational database", "rdbms"], "data structures": ["data structure"],
    "algorithms": ["algorithm"], "postman": [], "unit testing": ["unit tests"],
}
CANON = {alias.lower(): canonical for canonical, aliases in ALIASES.items() for alias in [canonical, *aliases]}
SKILLS = sorted(CANON, key=len, reverse=True)
BENCHMARK = Path(__file__).resolve().parents[1] / "data" / "skill_phrase_benchmark.csv"
TRAINED_MODEL = Path(__file__).resolve().parents[1] / "models" / "skill_phrase_model.joblib"


def norm(text):
    return re.sub(r"[ \t]+", " ", text.replace("\r\n", "\n").replace("\r", "\n").replace("–", "-").replace("—", "-")).strip()


def read_file(path):
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    if path.suffix.lower() == ".docx":
        doc = Document(str(path))
        return "\n".join([p.text for p in doc.paragraphs] + [" | ".join(cell.text for cell in row.cells) for table in doc.tables for row in table.rows])
    if path.suffix.lower() == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    raise ValueError("Supported formats: PDF, DOCX, TXT. Convert legacy DOC to DOCX.")


def _find_skill_terms(text):
    found = []
    negation = re.compile(r"\b(?:no|not|never|without|lack\w*|does not|do not|did not|has not|have not|not yet|haven't|hasn't|isn't|aren't)\b", re.I)
    contrast = re.compile(r"\b(?:but|however|although)\b", re.I)
    for alias in SKILLS:
        for match in re.finditer(r"(?<![a-z0-9+#.])" + re.escape(alias) + r"(?![a-z0-9+#.])", text, re.I):
            # Do not count a keyword as a demonstrated skill when the same clause explicitly negates it.
            clause_start = max(text.rfind("\n", 0, match.start()), text.rfind(".", 0, match.start()), text.rfind(";", 0, match.start())) + 1
            prefix = text[clause_start:match.start()]
            contrasts = list(contrast.finditer(prefix))
            if contrasts:
                prefix = prefix[contrasts[-1].end():]
            if negation.search(prefix):
                continue
            canonical = CANON[alias]
            if canonical not in found:
                found.append(canonical)
                break
    return found


def _phrase_rows(text):
    rows = []
    for line in text.splitlines():
        line = line.strip(" \t•*-\u2022")
        if not line:
            continue
        for piece in re.split(r"(?<=[.;])\s+|\s+[|]\s+", line):
            piece = piece.strip()
            if piece:
                rows.append(piece[:400])
    # Short chunks help long paragraphs where a skill appears after a non-skill clause.
    return list(dict.fromkeys(rows))[:2500]


def _load_benchmark():
    if BENCHMARK.exists():
        with BENCHMARK.open(encoding="utf-8", newline="") as handle:
            return [(row["phrase"], row["label"]) for row in csv.DictReader(handle) if row.get("phrase") and row.get("label") in {"SKILL", "OTHER"}]
    return [("Python programming", "SKILL"), ("REST API development", "SKILL"), ("I enjoy outdoor activities", "OTHER"), ("Worked with customers", "OTHER")]


@lru_cache(maxsize=1)
def _ml_model():
    if TRAINED_MODEL.exists():
        try:
            import joblib
            saved = joblib.load(TRAINED_MODEL)
            if hasattr(saved, "predict") and hasattr(saved, "predict_proba"):
                return saved
        except Exception:
            pass
    rows = _load_benchmark()
    texts = [phrase for phrase, _ in rows]
    labels = [label for _, label in rows]
    model = Pipeline([
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=1, sublinear_tf=True)),
        ("classifier", LogisticRegression(max_iter=1500, class_weight="balanced", random_state=42)),
    ])
    model.fit(texts, labels)
    return model


def _ml_classify(phrase):
    model = _ml_model()
    probabilities = model.predict_proba([phrase])[0]
    classes = list(model.classes_)
    idx = classes.index("SKILL")
    return float(probabilities[idx]), probabilities[idx] >= 0.50


def _ml_extract_skills(text):
    model = _ml_model()
    found, evidence = [], []
    for phrase in _phrase_rows(text):
        try:
            confidence, positive = _ml_classify(phrase)
        except Exception:
            continue
        if positive:
            terms = _find_skill_terms(phrase)
            if terms:
                evidence.append({"phrase": phrase[:180], "confidence": round(confidence, 3), "skills": terms})
                for term in terms:
                    if term not in found:
                        found.append(term)
    return found, evidence


def parse_resume(text):
    text = norm(text)
    lines = [line.strip(" •\t-") for line in text.splitlines() if line.strip()]
    sections = {"education": [], "experience": [], "projects": [], "certifications": [], "summary": []}
    active = "summary"
    rules = {
        "education": r"education|academic|qualifications?", "experience": r"experience|employment|work history|internships?",
        "projects": r"projects?|research", "certifications": r"certifications?|licenses|courses",
        "summary": r"summary|profile|objective|about",
    }
    for line in lines:
        found = next((key for key, pattern in rules.items() if re.fullmatch(rf"(?:{pattern})\s*:?", line, re.I)), None)
        if found:
            active = found
        else:
            sections[active].append(line)
    rule_skills = _find_skill_terms(text)
    ml_skills, ml_evidence = _ml_extract_skills(text)
    hybrid_skills = sorted(set(rule_skills) | set(ml_skills))
    def matches(pattern):
        return list(dict.fromkeys(match.group(0).strip() for match in re.finditer(pattern, text, re.I)))
    name = next((line for line in lines[:8] if not re.search(r"@|https?://|\d{3}|resume|linkedin|github", line, re.I) and len(line.split()) <= 5 and len(line) < 60), "")
    emails = matches(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
    phones = matches(r"(?<!\w)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,5}\)?[\s.-]?)?\d{5,10}(?!\w)")
    links = matches(r"https?://[^\s)>]+|(?:www\.)?linkedin\.com/in/[^\s)>]+|github\.com/[^\s)>]+")
    confidence = round(min(.98, .35 + min(len(text), 5000) / 8000 + .12 * bool(emails) + .08 * bool(hybrid_skills)), 2) if text.strip() else 0
    return {
        "name": name, "emails": emails, "phones": phones, "links": links,
        "skills": hybrid_skills, "rule_based_skills": sorted(rule_skills), "ml_based_skills": sorted(ml_skills),
        "ml_evidence": ml_evidence[:40], "education": sections["education"][:30],
        "experience": sections["experience"][:40], "projects": sections["projects"][:30],
        "certifications": sections["certifications"][:25], "summary": sections["summary"][:12],
        "extraction_method": "rule-based + trained phrase classifier + canonical normalization",
        "text_length": len(text), "parsing_confidence": confidence,
    }


def jd_skills(text, explicit=None):
    # When the recruiter supplies an explicit required-skills list, treat it as authoritative;
    # do not silently promote every preferred/contextual keyword in the full JD to a requirement.
    explicit_skills = {CANON.get(str(skill).strip().lower(), str(skill).strip().lower()) for skill in (explicit or []) if str(skill).strip()}
    if explicit_skills:
        return sorted(explicit_skills)
    return sorted(set(_find_skill_terms(text)))


def _similarity(jd, resume):
    try:
        matrix = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=12000).fit_transform([jd, resume])
        return float(cosine_similarity(matrix[0:1], matrix[1:2])[0, 0])
    except (ValueError, TypeError):
        return 0.0


def score(parsed, resume, jd, required):
    required = sorted({CANON.get(str(skill).strip().lower(), str(skill).strip().lower()) for skill in (required or jd_skills(jd)) if str(skill).strip()})
    rule_skills = set(parsed.get("rule_based_skills", parsed.get("skills", [])))
    ml_skills = set(parsed.get("ml_based_skills", []))
    hybrid_skills = set(parsed.get("skills", []))
    rule_matched = sorted(rule_skills.intersection(required))
    ml_matched = sorted(ml_skills.intersection(required))
    hybrid_matched = sorted(hybrid_skills.intersection(required))
    denominator = len(required) or 1
    rule_coverage = len(rule_matched) / denominator
    ml_coverage = len(ml_matched) / denominator
    hybrid_coverage = len(hybrid_matched) / denominator
    semantic = _similarity(jd, resume)
    evidence = min(1.0, (len(parsed.get("experience", [])) + len(parsed.get("projects", []))) / 8)
    parsing = float(parsed.get("parsing_confidence", 0))
    rule_score = round(100 * rule_coverage)
    ml_score = round(100 * ml_coverage)
    hybrid_score = round(100 * (.58 * hybrid_coverage + .22 * semantic + .12 * evidence + .08 * parsing))
    missing = sorted(set(required) - hybrid_skills)
    recommendations = []
    if missing:
        recommendations.append("If you genuinely have them, add evidence for relevant skills: " + ", ".join(missing[:12]) + ".")
    if not parsed.get("experience"):
        recommendations.append("Add a clearly labelled Experience or Internship section and quantify impact where possible.")
    if not parsed.get("education"):
        recommendations.append("Add a clearly labelled Education section with degree, institution, and dates.")
    if not parsed.get("emails"):
        recommendations.append("Add a professional contact email in selectable text.")
    if parsed.get("text_length", 0) < 500:
        recommendations.append("Extracted text is short; verify whether the PDF is scanned or extraction failed.")
    process_trace = [
        {"stage": "Document parsing", "component": "PDF/DOCX/TXT parser", "status": "complete", "detail": f"Extracted {parsed.get('text_length', 0)} characters; parsing confidence {round(parsing*100)}%."},
        {"stage": "Rule-based extraction", "component": "Skill ontology + regex aliases", "status": "complete", "detail": f"Found {len(rule_skills)} canonical skills; {len(rule_matched)} match the JD requirements."},
        {"stage": "ML-based extraction", "component": "TF-IDF character n-grams + Logistic Regression", "status": "complete", "detail": f"Classified resume phrases and retained {len(ml_skills)} canonical skills; {len(ml_matched)} match the JD requirements."},
        {"stage": "Resolution & normalization", "component": "Alias resolver", "status": "complete", "detail": "Mapped recognized aliases to canonical skill names and merged duplicate terms."},
        {"stage": "Semantic relevance", "component": "TF-IDF cosine similarity", "status": "complete", "detail": f"Resume/JD text similarity is {round(semantic*100, 1)}%."},
        {"stage": "Hybrid scoring", "component": "Weighted evidence aggregator", "status": "complete", "detail": "Combined skill coverage, semantic relevance, project/experience evidence, and parsing quality."},
    ]
    return {
        "score": hybrid_score, "score_label": "Hybrid ATS readiness estimate",
        "breakdown": {"required_skill_coverage": round(hybrid_coverage*100, 1), "semantic_relevance": round(semantic*100, 1), "experience_project_evidence": round(evidence*100, 1), "parsing_quality": round(parsing*100, 1)},
        "matched_skills": hybrid_matched, "missing_skills": missing, "required_skills": required,
        "semantic_similarity": round(semantic, 4), "recommendations": recommendations,
        "scoring_formula": "58% hybrid required-skill coverage + 22% TF-IDF relevance + 12% experience/project evidence + 8% parsing quality",
        "model_comparison": {
            "rule_based": {"name": "Rule-Based Model", "score": rule_score, "matched_skills": rule_matched, "missing_skills": sorted(set(required)-rule_skills), "formula": "Required-skill coverage × 100", "contribution": "Exact lexicon/pattern matching and alias rules"},
            "ml_based": {"name": "ML-Based Model", "score": ml_score, "matched_skills": ml_matched, "missing_skills": sorted(set(required)-ml_skills), "formula": "ML-classified skill phrase coverage × 100", "contribution": "Character n-gram TF-IDF + Logistic Regression phrase classification"},
            "hybrid": {"name": "Hybrid Architecture", "score": hybrid_score, "matched_skills": hybrid_matched, "missing_skills": missing, "formula": "58% coverage + 22% semantic relevance + 12% evidence + 8% parsing quality", "contribution": "Rule evidence + ML evidence + normalization + semantic relevance + evidence scoring"},
        },
        "component_outputs": {"rule_based_skills": sorted(rule_skills), "ml_based_skills": sorted(ml_skills), "resolved_hybrid_skills": sorted(hybrid_skills), "ml_phrase_evidence": parsed.get("ml_evidence", [])[:20]},
        "process_trace": process_trace,
        "caveat": "Advisory resume-to-JD alignment only; not a commercial ATS score or hiring decision. Human review is required.",
    }
