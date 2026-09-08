# Upload + Generate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `POST /upload`, `POST /generate/{file_id}`, and `GET /job/{job_id}` in the FastAPI backend, backed by a new `script_generator.py` module that extracts PDF text and calls Claude to produce a structured narration script JSON.

**Architecture:** `backend/script_generator.py` owns all PDF + Claude logic (extract_text, generate_script). `backend/main.py` stays HTTP-only — it calls into script_generator from a background task and writes job state to the in-memory `jobs` dict. No database.

**Tech Stack:** FastAPI, pdfplumber, anthropic-sdk, pytest, httpx (TestClient)

## Global Constraints

- Model: `claude-sonnet-4-6`, max_tokens=4096
- Script JSON shape: `{"file_id": str, "title": str, "slides": [{"index": int, "title": str, "narration": str, "bullets": list[str]}]}` — 5–8 slides, 2–4 bullets each
- API key via `os.environ["ANTHROPIC_API_KEY"]` — no python-dotenv
- `jobs` dict shape: `{"status": str, "result": dict | None, "error": str | None}`
- Upload limits: PDF only (content_type must be `application/pdf`), max 20 MB
- Generate retries Claude once on JSONDecodeError, then sets job to "error"
- No new top-level dependencies beyond what is already in `backend/requirements.txt` (`fastapi`, `uvicorn[standard]`, `anthropic`, `elevenlabs`, `pdfplumber`, `python-multipart`)
- Dev-only dependencies go in `backend/requirements-dev.txt`: `pytest`, `httpx`

---

### Task 1: `backend/script_generator.py` with unit tests

**Files:**
- Create: `backend/script_generator.py`
- Create: `backend/requirements-dev.txt`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_script_generator.py`

**Interfaces:**
- Produces:
  - `extract_text(pdf_path: Path) -> str` — joins page texts with `"\n\n"`, treats `None` pages as `""`
  - `generate_script(file_id: str, text: str) -> dict` — returns validated script dict with `file_id` injected; raises `ValueError` if `ANTHROPIC_API_KEY` missing; raises `json.JSONDecodeError` (after one retry) if Claude returns un-parseable JSON

---

- [ ] **Step 1: Create `backend/requirements-dev.txt`**

```
pytest
httpx
```

- [ ] **Step 2: Create `backend/tests/__init__.py`** (empty file)

- [ ] **Step 3: Create `backend/tests/conftest.py`** — adds backend dir to sys.path so tests can `import script_generator` and `import main`

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
```

- [ ] **Step 4: Write the failing tests for `extract_text`**

Create `backend/tests/test_script_generator.py`:

```python
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from script_generator import extract_text, generate_script


def _make_mock_pdf(pages):
    """pages: list of str|None — what each page's extract_text() returns."""
    mock_pages = []
    for text in pages:
        p = MagicMock()
        p.extract_text.return_value = text
        mock_pages.append(p)

    mock_pdf = MagicMock()
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.pages = mock_pages
    return mock_pdf


def test_extract_text_joins_pages_with_double_newline(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"placeholder")

    with patch("script_generator.pdfplumber.open", return_value=_make_mock_pdf(["First page", "Second page"])):
        result = extract_text(pdf_path)

    assert result == "First page\n\nSecond page"


def test_extract_text_treats_none_page_as_empty(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"placeholder")

    with patch("script_generator.pdfplumber.open", return_value=_make_mock_pdf([None])):
        result = extract_text(pdf_path)

    assert result == ""


def test_generate_script_returns_dict_with_file_id(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    script_body = {
        "title": "Test Document",
        "slides": [
            {
                "index": 0,
                "title": "Introduction",
                "narration": "This is the narration.",
                "bullets": ["Point A", "Point B"],
            }
        ],
    }
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(script_body))]

    with patch("script_generator.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = mock_response
        result = generate_script("file-abc", "some source text")

    assert result["file_id"] == "file-abc"
    assert result["title"] == "Test Document"
    assert len(result["slides"]) == 1
    assert mock_cls.return_value.messages.create.call_count == 1


def test_generate_script_raises_value_error_when_no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        generate_script("file-abc", "some text")


def test_generate_script_retries_once_on_invalid_json(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    valid_script = {
        "title": "Retry Test",
        "slides": [
            {
                "index": 0,
                "title": "S1",
                "narration": "Narration sentence.",
                "bullets": ["B1", "B2"],
            }
        ],
    }
    bad_response = MagicMock()
    bad_response.content = [MagicMock(text="not valid json {{{")]
    good_response = MagicMock()
    good_response.content = [MagicMock(text=json.dumps(valid_script))]

    with patch("script_generator.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.side_effect = [bad_response, good_response]
        result = generate_script("file-abc", "some text")

    assert result["title"] == "Retry Test"
    assert mock_cls.return_value.messages.create.call_count == 2


def test_generate_script_raises_on_persistent_invalid_json(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    bad_response = MagicMock()
    bad_response.content = [MagicMock(text="still not json")]

    with patch("script_generator.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = bad_response
        with pytest.raises(json.JSONDecodeError):
            generate_script("file-abc", "some text")

    assert mock_cls.return_value.messages.create.call_count == 2
```

- [ ] **Step 5: Run tests to confirm they fail (ImportError)**

```
cd backend && python -m pytest tests/test_script_generator.py -v
```

Expected: `ModuleNotFoundError: No module named 'script_generator'`

- [ ] **Step 6: Create `backend/script_generator.py`**

```python
import json
import os
from pathlib import Path

import anthropic
import pdfplumber

_SYSTEM_PROMPT = (
    "You are an expert educator creating a narrated slide deck from source material. "
    "Your output must be valid JSON and nothing else — no markdown fences, no commentary."
)

_USER_TEMPLATE = """\
Source text:
{text}

Produce a JSON object with this exact schema:
{{
  "title": "<overall document title>",
  "slides": [
    {{
      "index": <int starting at 0>,
      "title": "<slide title>",
      "narration": "<1-3 sentence paragraph suitable for text-to-speech>",
      "bullets": ["<key point>", ...]
    }}
  ]
}}

Rules:
- Generate between 5 and 8 slides.
- Each slide must have 2 to 4 bullets.
- Narration must be complete sentences, not bullet points.
- Return only the JSON object. No markdown, no explanation.\
"""


def extract_text(pdf_path: Path) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n\n".join(pages)


def generate_script(file_id: str, text: str) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    client = anthropic.Anthropic(api_key=api_key)

    def _call(messages: list) -> str:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            messages=messages,
        )
        return response.content[0].text.strip()

    user_msg = {"role": "user", "content": _USER_TEMPLATE.format(text=text)}
    raw = _call([user_msg])

    try:
        script = json.loads(raw)
    except json.JSONDecodeError:
        raw2 = _call([
            user_msg,
            {"role": "assistant", "content": raw},
            {"role": "user", "content": "That was not valid JSON. Return only the JSON object, nothing else."},
        ])
        script = json.loads(raw2)

    script["file_id"] = file_id
    return script
```

- [ ] **Step 7: Run tests and confirm they pass**

```
cd backend && python -m pytest tests/test_script_generator.py -v
```

Expected: 5 tests PASSED

- [ ] **Step 8: Commit**

```bash
git add backend/script_generator.py backend/requirements-dev.txt backend/tests/
git commit -m "feat: add script_generator module with extract_text and generate_script"
```

---

### Task 2: API routes in `backend/main.py` + integration tests + `.env.example`

**Files:**
- Modify: `backend/main.py`
- Create: `backend/tests/test_routes.py`
- Create: `backend/.env.example`

**Interfaces:**
- Consumes (from Task 1):
  - `extract_text(pdf_path: Path) -> str`
  - `generate_script(file_id: str, text: str) -> dict`
- Produces:
  - `POST /upload` → `{"file_id": str}`
  - `POST /generate/{file_id}` → `{"job_id": str}`
  - `GET /job/{job_id}` → `{"job_id": str, "status": str, "result": dict|null, "error": str|null}`

---

- [ ] **Step 1: Write the failing route tests**

Create `backend/tests/test_routes.py`:

```python
import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import main
from main import app, jobs

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state(tmp_path, monkeypatch):
    jobs.clear()
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    yield
    jobs.clear()


# ── /upload ──────────────────────────────────────────────────────────────────

def test_upload_pdf_returns_file_id():
    response = client.post(
        "/upload",
        files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 minimal"), "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert "file_id" in body
    assert len(body["file_id"]) == 36  # UUID format


def test_upload_non_pdf_returns_400():
    response = client.post(
        "/upload",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_upload_file_over_20mb_returns_400():
    big = b"A" * (21 * 1024 * 1024)
    response = client.post(
        "/upload",
        files={"file": ("big.pdf", io.BytesIO(big), "application/pdf")},
    )
    assert response.status_code == 400
    assert "20 MB" in response.json()["detail"]


# ── /generate ────────────────────────────────────────────────────────────────

def test_generate_returns_job_id(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    (tmp_path / "abc-123.pdf").write_bytes(b"%PDF-1.4")

    script_result = {"file_id": "abc-123", "title": "T", "slides": []}
    with patch("main.extract_text", return_value="text content"), \
         patch("main.generate_script", return_value=script_result):
        response = client.post("/generate/abc-123")

    assert response.status_code == 200
    assert "job_id" in response.json()


def test_generate_unknown_file_id_returns_404():
    response = client.post("/generate/nonexistent-file-id")
    assert response.status_code == 404


# ── /job ─────────────────────────────────────────────────────────────────────

def test_job_status_unknown_returns_404():
    response = client.get("/job/does-not-exist")
    assert response.status_code == 404


def test_job_status_reflects_background_task_result(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    (tmp_path / "abc-123.pdf").write_bytes(b"%PDF-1.4")

    script_result = {"file_id": "abc-123", "title": "Test", "slides": []}
    with patch("main.extract_text", return_value="text"), \
         patch("main.generate_script", return_value=script_result):
        gen = client.post("/generate/abc-123")

    job_id = gen.json()["job_id"]
    status = client.get(f"/job/{job_id}")
    assert status.status_code == 200
    body = status.json()
    assert body["job_id"] == job_id
    # TestClient runs background tasks synchronously, so status is "complete"
    assert body["status"] == "complete"
    assert body["result"]["title"] == "Test"
    assert body["error"] is None


def test_job_captures_generate_error(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    (tmp_path / "abc-123.pdf").write_bytes(b"%PDF-1.4")

    with patch("main.extract_text", return_value="text"), \
         patch("main.generate_script", side_effect=ValueError("ANTHROPIC_API_KEY environment variable is not set")):
        gen = client.post("/generate/abc-123")

    job_id = gen.json()["job_id"]
    status = client.get(f"/job/{job_id}")
    body = status.json()
    assert body["status"] == "error"
    assert "ANTHROPIC_API_KEY" in body["error"]
    assert body["result"] is None
```

- [ ] **Step 2: Run tests to confirm they fail (ImportError)**

```
cd backend && python -m pytest tests/test_routes.py -v
```

Expected: `ImportError` — routes don't exist yet

- [ ] **Step 3: Replace `backend/main.py` with the full implementation**

```python
import json
import pathlib
import uuid

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile

from script_generator import extract_text, generate_script

app = FastAPI(title="learnflow-ai")

UPLOADS_DIR = pathlib.Path("uploads")

# In-memory job store. Keys are job_id strings.
# Each value: {"status": str, "result": dict | None, "error": str | None}
jobs: dict[str, dict] = {}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 20 MB limit")
    file_id = str(uuid.uuid4())
    UPLOADS_DIR.mkdir(exist_ok=True)
    (UPLOADS_DIR / f"{file_id}.pdf").write_bytes(contents)
    return {"file_id": file_id}


@app.post("/generate/{file_id}")
def generate(file_id: str, background_tasks: BackgroundTasks) -> dict:
    pdf_path = UPLOADS_DIR / f"{file_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"No uploaded file with id {file_id!r}")
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "pending", "result": None, "error": None}
    background_tasks.add_task(_run_generate, job_id, file_id, pdf_path)
    return {"job_id": job_id}


def _run_generate(job_id: str, file_id: str, pdf_path: pathlib.Path) -> None:
    jobs[job_id]["status"] = "running"
    try:
        text = extract_text(pdf_path)
        script = generate_script(file_id, text)
        script_path = pdf_path.parent / f"{file_id}_script.json"
        script_path.write_text(json.dumps(script))
        jobs[job_id] = {"status": "complete", "result": script, "error": None}
    except Exception as exc:
        jobs[job_id] = {"status": "error", "result": None, "error": str(exc)}


@app.get("/job/{job_id}")
def job_status(job_id: str) -> dict:
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"No job with id {job_id!r}")
    job = jobs[job_id]
    return {"job_id": job_id, **job}
```

- [ ] **Step 4: Run tests and confirm they pass**

```
cd backend && python -m pytest tests/test_routes.py -v
```

Expected: 8 tests PASSED

- [ ] **Step 5: Run full test suite to confirm nothing broke**

```
cd backend && python -m pytest tests/ -v
```

Expected: 13 tests PASSED (5 from test_script_generator + 8 from test_routes)

- [ ] **Step 6: Create `backend/.env.example`**

```bash
# Copy to .env and fill in your values before starting the backend.
# The backend reads env vars directly via os.environ — no python-dotenv required.
# Set these in your shell or a .env file loaded by your process manager.

ANTHROPIC_API_KEY=sk-ant-...   # Required for POST /generate
```

- [ ] **Step 7: Commit**

```bash
git add backend/main.py backend/tests/test_routes.py backend/.env.example
git commit -m "feat: implement /upload, /generate, /job routes with background task pipeline"
```
