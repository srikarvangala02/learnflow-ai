# Remotion Renderer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the script JSON from `POST /generate` into Remotion slide compositions and add `POST /render/{job_id}` to the FastAPI backend, which shells out to `npx remotion render` in a background task.

**Architecture:** Two new Remotion components (`LearnFlowVideo.tsx` routes frames to slides; `Slide.tsx` renders one slide as title + bullets) replace the placeholder `Root.tsx`. The backend route reads the completed generate job's script JSON, spawns a background task that calls `subprocess.run` to invoke `npx remotion render --props`, and tracks the render as a new job in the in-memory `jobs` store.

**Tech Stack:** Remotion 4.x, TypeScript (`react-jsx` transform — no React import needed), FastAPI, pytest, `unittest.mock`

**Spec:** `docs/superpowers/specs/2026-08-31-remotion-renderer-design.md`

## Global Constraints

- `FRAMES_PER_SLIDE = 150` (5 s at 30 fps) — defined in `render/src/LearnFlowVideo.tsx`, imported by `Root.tsx`
- Composition id must be `"LearnFlowVideo"` (referenced by the subprocess call)
- `calculateMetadata` computes `durationInFrames = Math.max(slides.length, 1) * FRAMES_PER_SLIDE`
- Slide layout: dark background `#1a1a2e`, title `#e0e0ff` 64 px, bullets `#c0c0e0` 40 px, padding 80 px
- No explicit `import React from 'react'` — tsconfig uses `jsx: "react-jsx"` (new JSX transform)
- `POST /render/{job_id}` — 404 if job unknown, 400 if job status is not `"complete"`
- Background task subprocess: `["npx", "remotion", "render", "src/index.ts", "LearnFlowVideo", <out_path>, "--props", <props_path>]`, `cwd = render/` (resolved absolute)
- Output path: `render/out/{render_job_id}.mp4` (resolved absolute)
- Props path: `UPLOADS_DIR / f"{file_id}_script.json"` (resolved absolute) — already written by the generate step
- On subprocess `returncode == 0`: job → `{"status": "complete", "result": {"video_path": str(out_path)}, "error": None}`
- On non-zero returncode: job → `{"status": "error", "result": None, "error": result.stderr.decode()}`

---

### Task 1: Remotion slide components

**Files:**
- Create: `render/src/LearnFlowVideo.tsx`
- Create: `render/src/Slide.tsx`
- Modify: `render/src/Root.tsx` (full replacement)

**Interfaces:**
- Produces:
  - `SlideData` type (exported from `LearnFlowVideo.tsx`)
  - `VideoProps` type (exported from `LearnFlowVideo.tsx`)
  - `FRAMES_PER_SLIDE: number` constant (exported from `LearnFlowVideo.tsx`)
  - `LearnFlowVideo({ title, slides }: VideoProps)` component (exported from `LearnFlowVideo.tsx`)
  - Composition id `"LearnFlowVideo"` registered in `Root.tsx`

---

- [ ] **Step 1: Ensure render dependencies are installed**

```bash
cd render
ls node_modules 2>/dev/null || npm install
```

Expected: `node_modules/` directory with `remotion`, `@remotion/cli`, `react`, `react-dom` present.

- [ ] **Step 2: Create `render/src/LearnFlowVideo.tsx`**

```tsx
import { useCurrentFrame } from 'remotion'
import { Slide } from './Slide'

export type SlideData = {
  index: number
  title: string
  narration: string
  bullets: string[]
}

export type VideoProps = {
  title: string
  slides: SlideData[]
}

export const FRAMES_PER_SLIDE = 150 // 5 s at 30 fps

export function LearnFlowVideo({ slides }: VideoProps) {
  const frame = useCurrentFrame()
  const slideIndex = Math.min(Math.floor(frame / FRAMES_PER_SLIDE), slides.length - 1)
  const slide = slides[slideIndex]
  return <Slide slide={slide} />
}
```

- [ ] **Step 3: Create `render/src/Slide.tsx`**

```tsx
import { SlideData } from './LearnFlowVideo'

export function Slide({ slide }: { slide: SlideData }) {
  return (
    <div
      style={{
        background: '#1a1a2e',
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        padding: '80px',
        boxSizing: 'border-box',
      }}
    >
      <h1
        style={{
          color: '#e0e0ff',
          fontFamily: 'sans-serif',
          fontSize: '64px',
          margin: '0 0 48px 0',
        }}
      >
        {slide.title}
      </h1>
      <ul
        style={{
          color: '#c0c0e0',
          fontFamily: 'sans-serif',
          fontSize: '40px',
          lineHeight: '1.6',
          paddingLeft: '48px',
          margin: 0,
        }}
      >
        {slide.bullets.map((b, i) => (
          <li key={i}>{b}</li>
        ))}
      </ul>
    </div>
  )
}
```

- [ ] **Step 4: Replace `render/src/Root.tsx` entirely**

```tsx
import { Composition, CalculateMetadataFunction } from 'remotion'
import { LearnFlowVideo, VideoProps, FRAMES_PER_SLIDE } from './LearnFlowVideo'

const calculateMetadata: CalculateMetadataFunction<VideoProps> = ({ props }) => ({
  durationInFrames: Math.max(props.slides.length, 1) * FRAMES_PER_SLIDE,
})

const defaultProps: VideoProps = {
  title: 'Untitled',
  slides: [{ index: 0, title: 'Slide', narration: '', bullets: [''] }],
}

export function Root() {
  return (
    <Composition
      id="LearnFlowVideo"
      component={LearnFlowVideo}
      calculateMetadata={calculateMetadata}
      durationInFrames={150}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={defaultProps}
    />
  )
}
```

- [ ] **Step 5: Type-check to verify it compiles**

```bash
cd render && npx tsc --noEmit
```

Expected: no errors, exits 0. If you see errors about `CalculateMetadataFunction` not exported from `remotion`, use this alternative type annotation:

```tsx
// Alternative if CalculateMetadataFunction is not available in your Remotion version:
const calculateMetadata = async ({ props }: { props: VideoProps }) => ({
  durationInFrames: Math.max(props.slides.length, 1) * FRAMES_PER_SLIDE,
})
```

- [ ] **Step 6: Commit**

```bash
git add render/src/LearnFlowVideo.tsx render/src/Slide.tsx render/src/Root.tsx
git commit -m "feat: add Remotion slide components with dynamic duration"
```

---

### Task 2: Backend render route and tests

**Files:**
- Modify: `backend/main.py`
- Create: `backend/tests/test_render_route.py`

**Interfaces:**
- Consumes (from existing code):
  - `jobs: dict[str, dict]` — in-memory store in `main.py`
  - `UPLOADS_DIR: pathlib.Path` — module-level var in `main.py`
  - `GET /job/{job_id}` — already implemented, used to poll render status
- Produces:
  - `POST /render/{job_id}` → `{"job_id": str}` where `job_id` is a new render job id

---

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_render_route.py`:

```python
import json
import pathlib
from unittest.mock import MagicMock, patch

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


def _seed_complete_generate_job(tmp_path: pathlib.Path, file_id: str = "abc-123") -> str:
    """Insert a complete generate job into `jobs` and write its script JSON to disk."""
    script = {
        "file_id": file_id,
        "title": "Test Doc",
        "slides": [
            {
                "index": 0,
                "title": "Introduction",
                "narration": "Intro narration.",
                "bullets": ["Point A", "Point B"],
            }
        ],
    }
    (tmp_path / f"{file_id}_script.json").write_text(json.dumps(script))
    job_id = "generate-job-001"
    jobs[job_id] = {"status": "complete", "result": script, "error": None}
    return job_id


def _mock_subprocess(returncode: int = 0, stderr: bytes = b"") -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stderr = stderr
    return m


# ── POST /render/{job_id} ────────────────────────────────────────────────────

def test_render_returns_job_id(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    job_id = _seed_complete_generate_job(tmp_path)

    with patch("main.subprocess.run", return_value=_mock_subprocess(0)):
        response = client.post(f"/render/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert "job_id" in body
    assert len(body["job_id"]) == 36  # UUID format


def test_render_unknown_job_returns_404():
    response = client.post("/render/does-not-exist")
    assert response.status_code == 404


def test_render_incomplete_job_returns_400(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    jobs["pending-job"] = {"status": "pending", "result": None, "error": None}
    response = client.post("/render/pending-job")
    assert response.status_code == 400
    assert "complete" in response.json()["detail"].lower()


def test_render_error_job_returns_400(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    jobs["error-job"] = {"status": "error", "result": None, "error": "Claude failed"}
    response = client.post("/render/error-job")
    assert response.status_code == 400


# ── Background task outcomes ─────────────────────────────────────────────────

def test_successful_render_sets_job_complete(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    job_id = _seed_complete_generate_job(tmp_path)

    with patch("main.subprocess.run", return_value=_mock_subprocess(0)):
        gen = client.post(f"/render/{job_id}")

    render_job_id = gen.json()["job_id"]
    status = client.get(f"/job/{render_job_id}")
    assert status.status_code == 200
    body = status.json()
    assert body["status"] == "complete"
    assert "video_path" in body["result"]
    assert body["result"]["video_path"].endswith(".mp4")
    assert body["error"] is None


def test_failed_render_sets_job_error(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    job_id = _seed_complete_generate_job(tmp_path)

    with patch("main.subprocess.run", return_value=_mock_subprocess(1, b"npx: command not found")):
        gen = client.post(f"/render/{job_id}")

    render_job_id = gen.json()["job_id"]
    status = client.get(f"/job/{render_job_id}")
    body = status.json()
    assert body["status"] == "error"
    assert "npx" in body["error"]
    assert body["result"] is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && python -m pytest tests/test_render_route.py -v
```

Expected: `ImportError` or `404` failures — `POST /render` doesn't exist yet.

- [ ] **Step 3: Add `import subprocess` and the render route to `backend/main.py`**

Add `import subprocess` at the top (with the other stdlib imports). Then add the route and background task after the existing `job_status` function:

```python
import subprocess
```

```python
@app.post("/render/{job_id}")
def render(job_id: str, background_tasks: BackgroundTasks) -> dict:
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"No job with id {job_id!r}")
    job = jobs[job_id]
    if job["status"] != "complete":
        raise HTTPException(
            status_code=400,
            detail=f"Generate job {job_id!r} is not complete (status: {job['status']!r})",
        )
    script = job["result"]
    render_job_id = str(uuid.uuid4())
    jobs[render_job_id] = {"status": "pending", "result": None, "error": None}
    background_tasks.add_task(_run_remotion_render, render_job_id, script)
    return {"job_id": render_job_id}


def _run_remotion_render(render_job_id: str, script: dict) -> None:
    jobs[render_job_id]["status"] = "running"
    try:
        file_id = script["file_id"]
        props_path = (UPLOADS_DIR / f"{file_id}_script.json").resolve()
        out_path = (pathlib.Path("render") / "out" / f"{render_job_id}.mp4").resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [
                "npx", "remotion", "render",
                "src/index.ts",
                "LearnFlowVideo",
                str(out_path),
                "--props", str(props_path),
            ],
            cwd=str(pathlib.Path("render").resolve()),
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            jobs[render_job_id] = {
                "status": "complete",
                "result": {"video_path": str(out_path)},
                "error": None,
            }
        else:
            jobs[render_job_id] = {
                "status": "error",
                "result": None,
                "error": result.stderr.decode(),
            }
    except Exception as exc:
        jobs[render_job_id] = {"status": "error", "result": None, "error": str(exc)}
```

The full updated `backend/main.py` in context (complete file, copy this verbatim):

```python
import json
import pathlib
import subprocess
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


@app.post("/render/{job_id}")
def render(job_id: str, background_tasks: BackgroundTasks) -> dict:
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"No job with id {job_id!r}")
    job = jobs[job_id]
    if job["status"] != "complete":
        raise HTTPException(
            status_code=400,
            detail=f"Generate job {job_id!r} is not complete (status: {job['status']!r})",
        )
    script = job["result"]
    render_job_id = str(uuid.uuid4())
    jobs[render_job_id] = {"status": "pending", "result": None, "error": None}
    background_tasks.add_task(_run_remotion_render, render_job_id, script)
    return {"job_id": render_job_id}


def _run_remotion_render(render_job_id: str, script: dict) -> None:
    jobs[render_job_id]["status"] = "running"
    try:
        file_id = script["file_id"]
        props_path = (UPLOADS_DIR / f"{file_id}_script.json").resolve()
        out_path = (pathlib.Path("render") / "out" / f"{render_job_id}.mp4").resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [
                "npx", "remotion", "render",
                "src/index.ts",
                "LearnFlowVideo",
                str(out_path),
                "--props", str(props_path),
            ],
            cwd=str(pathlib.Path("render").resolve()),
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            jobs[render_job_id] = {
                "status": "complete",
                "result": {"video_path": str(out_path)},
                "error": None,
            }
        else:
            jobs[render_job_id] = {
                "status": "error",
                "result": None,
                "error": result.stderr.decode(),
            }
    except Exception as exc:
        jobs[render_job_id] = {"status": "error", "result": None, "error": str(exc)}
```

- [ ] **Step 4: Run the render route tests**

```bash
cd backend && python -m pytest tests/test_render_route.py -v
```

Expected: 6 tests PASSED

- [ ] **Step 5: Run the full test suite to confirm no regressions**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: 20 tests PASSED (14 existing + 6 new)

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/tests/test_render_route.py
git commit -m "feat: add /render route with Remotion subprocess background task"
```
