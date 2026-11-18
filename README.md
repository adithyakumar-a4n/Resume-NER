# Resume_NER ATS

A local full-stack prototype for comparing a resume with a job description. It combines rule-based skill matching, an ML-assisted phrase classifier, and a weighted hybrid score, then shows the extracted evidence so a person can review the result.

> **Important:** This is a learning and decision-support prototype, not a validated hiring system. Its benchmark is small and phrase-level. Scores must not be used as hiring decisions, and the application should not be used to infer or score protected characteristics.

## What it does

- Recruiters can register, publish job descriptions, and provide an explicit list of required skills.
- Applicants can register and upload PDF, DOCX, or TXT resumes.
- The backend extracts resume text and organizes basic profile sections.
- Three approaches are shown separately:
  - **Rule-based:** skill dictionary, aliases, and simple negation handling.
  - **ML-assisted:** character n-gram TF-IDF with Logistic Regression to classify short phrases as `SKILL` or `OTHER`.
  - **Hybrid:** combines normalized skill evidence, resume/JD similarity, project and experience signals, and parsing confidence.
- Recruiters can inspect matched/missing skills, phrase evidence, model contributions, and the saved benchmark report.

## Project layout

```text
Resume_NER/
├── backend/
│   ├── app/                 # FastAPI routes, auth, parsing and scoring
│   ├── data/                # Local SQLite data, uploads and phrase benchmark
│   ├── models/               # Trained phrase classifier
│   ├── reports/              # Saved benchmark summary
│   └── requirements.txt
├── frontend/
│   ├── src/                  # React interface
│   └── package.json
├── notebooks/                # Model training and comparison notebook
├── docs/                     # API and demo notes
└── backend/tests/             # Regression tests
```

## Requirements

- Python 3.10 or newer
- Node.js 20 or newer
- Windows, macOS, or Linux

## Run locally

### 1. Start the backend

From the project root:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Set a development secret in the same PowerShell terminal. Generate a new value rather than reusing the example below:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
$env:SECRET_KEY = "paste-the-generated-value-here"
$env:APP_ENV = "development"
python -m uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`. Interactive API documentation is at `http://127.0.0.1:8000/docs`.

### 2. Start the frontend

Open a second terminal at the project root:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL printed by the command (normally `http://localhost:5173`). The frontend talks to `http://127.0.0.1:8000/api` by default. To use another backend URL, copy `frontend/.env.example` to `frontend/.env.local` and edit `VITE_API_BASE_URL` before starting Vite.

### 3. Create accounts and try the workflow

There are no pre-created demo accounts. Use **Create account** in the interface to register one recruiter account and one applicant account.

1. Sign in as a recruiter and publish a job description. Enter explicit required skills when possible.
2. Sign in as an applicant and upload a test resume for that job.
3. Sign back in as the recruiter and run the analysis.
4. Review the three score cards, skill evidence, extracted profile, and model-evaluation page. The six-step progress animation is a visual guide, not a server-reported progress stream.

Use fictional or consented test resumes only. Uploaded documents and extracted text are stored on the machine running the backend. The `.gitignore` excludes the local database, uploads, and search index.

## Model and evaluation

The phrase classifier uses character n-gram TF-IDF features and Logistic Regression. The training notebook is `notebooks/Resume_NER_Model_Training.ipynb`.

The saved benchmark report was generated on **22 October 2026** using 115 labelled phrases, with 86 training examples and 29 held-out examples (stratified split, `random_state=42`):

| Metric          | Recorded result |
| --------------- | --------------: |
| Accuracy        |          75.86% |
| Macro F1        |          75.75% |
| SKILL precision |          76.92% |
| SKILL recall    |          71.43% |

These figures describe the phrase-classification experiment only. They are not entity-level NER metrics, full-resume extraction results, or evidence of performance on unseen candidates. The held-out sample is small; a larger independently labelled dataset is needed before drawing stronger conclusions. The evaluation report and notebook preserve the confusion matrix and error examples so the limitations can be inspected.

## Security and privacy notes

- Demo accounts are disabled by default. Optional demo seeding requires `ENABLE_DEMO_ACCOUNTS=true` and explicit passwords in environment variables.
- Set a unique `SECRET_KEY` before deployment. With `APP_ENV=production`, the backend rejects the development placeholder and secrets shorter than 32 characters.
- Resume text is stored with its application record and is not added to the shared job-description search index.
- Search indexes job descriptions only. The index filters out legacy records tagged as resumes.
- Do not commit `.env` files, databases, uploaded resumes, logs, or real candidate data.
- Scanned image-only PDFs need OCR before upload. Convert legacy `.doc` files to `.docx`.

## Tests

Install the development dependencies and run the tests:

```powershell
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Further reading

- [API route guide](docs/API.md)
- [Demo walkthrough](docs/DEMO_GUIDE.md)
- [Validation notes](docs/VALIDATION.md)
