# Upload + Generate Design

**Date:** 2026-08-28
**Scope:** Implement `POST /upload`, `POST /generate/{file_id}`, and `GET /job/{job_id}` in the FastAPI backend.

---

## 1. Goal

Accept a PDF, extract its text, and use Claude to produce a structured narration script (5–8 slides). The script JSON is the contract consumed by all downstream pipeline stages (Remotion renderer, quiz generator, eval).

---

## 2. Files

**Create:**

- `backend/script_generator.py` — PDF text extraction + Claude prompt + JSON parsing
- `backend/.env.example` — documents required env vars

**Modify:**

- `backend/main.py` — implement `/upload`, `/generate/{file_id}`, `GET /job/{job_id}`; upgrade `jobs` store

---

## 3. Script JSON Schema

```json
{
  "file_id": "abc-123",
  "title": "Introduction to Transformers",
  "slides": [
    {
      "index": 0,
      "title": "What is a Transformer?",
      "narration": "A transformer is a neural network architecture that uses self-attention to process sequences in parallel rather than recurrently.",
      "bullets": ["Introduced in 2017", "Uses self-attention", "No recurrence"]
    }
  ]
}
```

- 5–8 slides
- 2–4 bullets per slide
- `narration` is a full paragraph (1–3 sentences) suitable for TTS

---

## 4. API Surface

```
POST /upload
  Body:    multipart/form-data, field "file" (PDF)
  Returns: {"file_id": str}
  Errors:  400 if content_type != application/pdf or file > 20 MB

POST /generate/{file_id}
  Returns: {"job_id": str}   — starts background task immediately
  Errors:  404 if uploads/{file_id}.pdf does not exist

GET /job/{job_id}
  Returns: {
    "job_id": str,
    "status": "pending" | "running" | "complete" | "error",
    "result": <script JSON> | null,
    "error": str | null
  }
  Errors:  404 if job_id not in jobs store
```

---

## 5. `script_generator.py`

### `extract_text(pdf_path: Path) -> str`

- Opens PDF with `pdfplumber`
- Concatenates text from all pages with `"\n\n"` separator
- Returns raw string

### `generate_script(file_id: str, text: str) -> dict`

- Reads `ANTHROPIC_API_KEY` from `os.environ`; raises `ValueError` if missing
- Calls `anthropic.Anthropic().messages.create()` with:
  - model: `claude-sonnet-4-6`
  - max_tokens: 4096
  - System prompt: educator creating a narrated slide deck
  - User message: source text + JSON schema instruction (5–8 slides, title/narration/bullets)
- Parses response as JSON
- On `json.JSONDecodeError`: retries once with a stricter "return only valid JSON" prompt
- Returns validated dict matching the schema above

---

## 6. `main.py` Changes

### `jobs` store upgrade

```python
# Before
jobs: dict[str, str] = {}

# After
jobs: dict[str, dict] = {}
# Each value: {"status": str, "result": dict | None, "error": str | None}
```

### Background task function

```python
def _run_generate(job_id: str, file_id: str, pdf_path: Path) -> None:
    jobs[job_id]["status"] = "running"
    try:
        text = extract_text(pdf_path)
        script = generate_script(file_id, text)
        # Persist to disk
        script_path = pdf_path.parent / f"{file_id}_script.json"
        script_path.write_text(json.dumps(script))
        jobs[job_id] = {"status": "complete", "result": script, "error": None}
    except Exception as e:
        jobs[job_id] = {"status": "error", "result": None, "error": str(e)}
```

---

## 7. Error Handling

| Scenario | Behaviour |
|---|---|
| Upload — wrong content type | `400 Bad Request` |
| Upload — file > 20 MB | `400 Bad Request` |
| Generate — file_id not on disk | `404 Not Found` |
| Generate — `ANTHROPIC_API_KEY` missing | job → `"error"`, error string in job record |
| Generate — Claude returns invalid JSON | retry once; if still invalid, job → `"error"` |
| Job poll — unknown job_id | `404 Not Found` |

---

## 8. Environment Variables

```bash
ANTHROPIC_API_KEY=sk-ant-...   # required for /generate
```

Loaded via `os.environ` — no `python-dotenv` dependency. For local dev, set in shell before starting uvicorn.

---

## 9. Out of Scope

- Authentication
- Persistent storage (DB) — `jobs` dict is in-memory only
- PDF page limit / chunking for very long documents
- Streaming Claude response
- Frontend wiring (covered in a later feature)
