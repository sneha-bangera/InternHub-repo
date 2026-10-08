# InternHub: Resume Alignment feature rules

Stack: Python, FastAPI, Next.js, PostgreSQL, Celery+Redis, sentence-transformers,
JWT auth with Redis refresh rotation.

- Follow existing folder structure, naming, error handling and config patterns.
- Reuse existing auth dependencies, DB session and embedding code. Don't duplicate.
- Don't refactor or break existing features. Touch only what's needed.
- Use the repo's migration tool for every schema change.
- NEVER fabricate resume content. LLM output may only rephrase, reorder and
  emphasize facts already in the user's profile.
- All LLM calls go through one LLMService (provider set by env, default Groq)
  with timeout, retry, and Pydantic-validated JSON output.
- Users never supply raw LaTeX. All user values pass through a latex_escape filter.
- Add pytest tests for backend logic. List new env vars in .env.example.
- After each task, list files changed and how to test.