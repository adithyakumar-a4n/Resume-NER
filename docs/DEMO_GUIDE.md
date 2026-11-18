# Local Demo Guide

## Start the application

1. Follow the [README setup steps](../README.md#run-locally).
2. Open the frontend in a browser.
3. Register a recruiter account and publish a job description with an explicit required-skills list.
4. Register an applicant account, choose the published role, and upload a fictional or consented PDF, DOCX, or TXT resume.
5. Sign back in as the recruiter and run the analysis.
6. Review the Rule-Based, ML-Based, and Hybrid results, matched/missing skills, phrase evidence, processing trace, and recommendations.
7. Open the ML Evaluation page to inspect the saved held-out phrase-classification report.

No demo account or candidate PDF is bundled. This avoids shipping fixed credentials or sample files that could be mistaken for real candidate information.

## What the scores mean

- **Rule-Based:** recognized skill names and aliases, with basic handling of explicit negation.
- **ML-Based:** a character n-gram TF-IDF and Logistic Regression classifier labels short phrases as `SKILL` or `OTHER`; accepted phrases are mapped back to the known skill lexicon.
- **Hybrid:** merges rule and ML evidence, then combines skill coverage, resume/JD similarity, experience/project signals, and parsing confidence.

The notebook's curated benchmark is a reproducible demonstration, not a representative hiring dataset. Phrase-level metrics are not span-level NER results. All outputs require human review; the app is not a commercial ATS integration or an automated hiring system.

Scanned PDFs need OCR before upload. Convert legacy `.doc` files to `.docx`.
