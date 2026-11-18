# Validation Notes

This file separates checks that have been recorded from checks that still need to be run in a clean, network-enabled development environment.

## Previously recorded checks

The supplied build record for this project reports:

- Python source compilation completed.
- Notebook JSON and code-cell syntax checks completed.
- The training notebook executed and produced the saved classifier and benchmark metrics.
- Pipeline smoke checks were run on two fictional test resumes; the positive example scored higher than the negative example.
- The frontend JSX parser reported no syntax diagnostics.

The earlier full Vite bundle build could not complete because the environment could not resolve the npm package registry. The current preparation environment also lacks the optional `python-jose` and `passlib` packages needed to execute the full FastAPI authentication routes; they are declared in `backend/requirements.txt`. These are historical/partial checks, not a claim that the current cleaned copy has just passed every integration test.

## Current regression coverage

The cleaned project adds six regression checks for job-only search indexing and skill parsing edge cases. These tests were run in the preparation environment and passed (6 passed). Run them again from a fresh environment:

```powershell
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Then, in `frontend`, run `npm install` followed by `npm run build` in an environment with access to the npm registry.

## Known limitations

- The labelled phrase benchmark contains 115 examples and only 29 held-out test examples.
- Phrase classification is not full-resume named-entity recognition.
- PDF text extraction does not perform OCR on scanned documents.
- The application needs a security review, privacy policy, retention controls, larger independent evaluation, and fairness testing before any real recruitment use.
