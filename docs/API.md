# API Routes

Protected routes require `Authorization: Bearer <token>`.
- GET `/api/health`
- POST `/api/auth/register` `{name,email,password,role}`
- POST `/api/auth/login` `{email,password}`
- GET `/api/me`
- GET/POST `/api/jobs` (POST recruiter only; explicit required skills are authoritative when supplied)
- POST `/api/applications?job_id=ID` multipart `file` (applicant only)
- GET `/api/applications` role-scoped list
- POST `/api/applications/{id}/analyze` (recruiter, own job only): returns the hybrid report, three-model comparison, component outputs, and processing trace
- GET `/api/applications/{id}` role-scoped detail
- GET `/api/search?q=...` (authenticated; searches job descriptions only)

Interactive docs: http://127.0.0.1:8000/docs
