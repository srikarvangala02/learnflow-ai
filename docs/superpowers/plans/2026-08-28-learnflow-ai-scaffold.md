# learnflow-ai Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the four-folder project structure (backend, frontend, render, eval) with minimal skeleton files that each run/build successfully, plus an updated README and .gitignore.

**Architecture:** FastAPI backend shells out to the Remotion CLI as a background subprocess job; frontend is a Vite+React+TS placeholder; the render folder is a standalone Remotion TypeScript project; eval holds two stub Python functions. Nothing is wired end-to-end in this scaffold.

**Tech Stack:** Python 3.11+ / FastAPI, Vite 6 + React 18 + TypeScript 5, Remotion 4 + TypeScript 5, ElevenLabs SDK, Anthropic SDK, pdfplumber

## Global Constraints

- All JS projects use TypeScript (strict mode, `noEmit: true` for type-checking).
- Remotion version: `^4.0.0`; React version: `^18.3.1`; Vite version: `^6.0.0`.
- No database, no Docker, no auth in this scaffold.
- Job state is in-memory only (`jobs: dict` in `backend/main.py`).
- The render CLI entry point is always passed explicitly as `src/index.ts` in npm scripts (Remotion v4 does not support `Config.setEntryPoint()`).
- No actual API calls to Claude or ElevenLabs in this scaffold.

---

## File Map

**Create:**

- `backend/main.py` — FastAPI app: health check + commented route stubs + background task skeleton
- `backend/requirements.txt` — Python deps
- `frontend/index.html` — Vite HTML entry
- `frontend/package.json` — Vite + React + TS deps + scripts
- `frontend/tsconfig.json` — TS config for frontend
- `frontend/vite.config.ts` — Vite plugin config
- `frontend/src/main.tsx` — React DOM mount
- `frontend/src/App.tsx` — Placeholder component
- `render/package.json` — Remotion + React + TS deps + scripts
- `render/tsconfig.json` — TS config for render project
- `render/remotion.config.ts` — Remotion concurrency config
- `render/src/index.ts` — `registerRoot` entry point
- `render/src/Root.tsx` — `<Composition>` definition
- `eval/eval.py` — Two stub functions
- `eval/results/.gitkeep` — Tracks empty directory in git

**Modify:**

- `README.md` — Replace stub with full skeleton (pitch, arch, tech stack, scope, setup)
- `.gitignore` — Append `node_modules/`, `render/out/`, `backend/uploads/`, `*.mp4`, `*.mp3`, `*.wav`

---

## Task 1: Backend scaffold

**Files:**

- Create: `backend/main.py`
- Create: `backend/requirements.txt`

**Interfaces:**

- Produces: `GET /health` → `{"status": "ok"}`; job status shape `{"job_id": str, "status": "pending|running|complete|error"}`

- [ ] **Step 1: Create `backend/requirements.txt`**

```text
fastapi
uvicorn[standard]
anthropic
elevenlabs
pdfplumber
python-multipart
```

- [ ] **Step 2: Create `backend/main.py`**

```python
import subprocess
import uuid

from fastapi import BackgroundTasks, FastAPI

app = FastAPI(title="learnflow-ai")

# In-memory job store. Keys are job_id strings; values are status strings.
jobs: dict[str, str] = {}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /upload
# ---------------------------------------------------------------------------
# Accept: UploadFile (PDF)
# Action: Save to backend/uploads/{file_id}.pdf
# Return: {"file_id": str}
#
# from fastapi import UploadFile, File
# import shutil, pathlib
#
# @app.post("/upload")
# async def upload(file: UploadFile = File(...)) -> dict:
#     file_id = str(uuid.uuid4())
#     dest = pathlib.Path("uploads") / f"{file_id}.pdf"
#     dest.parent.mkdir(exist_ok=True)
#     with dest.open("wb") as f:
#         shutil.copyfileobj(file.file, f)
#     return {"file_id": file_id}


# ---------------------------------------------------------------------------
# POST /generate/{file_id}
# ---------------------------------------------------------------------------
# Action: Extract text with pdfplumber, call Claude API to produce a
#         structured script JSON, persist to uploads/{file_id}_script.json.
# Return: {"job_id": str}
#
# @app.post("/generate/{file_id}")
# def generate(file_id: str) -> dict:
#     job_id = str(uuid.uuid4())
#     jobs[job_id] = "pending"
#     # TODO: pdfplumber.open(...) → anthropic.Anthropic().messages.create(...)
#     return {"job_id": job_id}


# ---------------------------------------------------------------------------
# POST /render/{job_id}
# ---------------------------------------------------------------------------
# Action: Enqueue _run_remotion_render as a background task.
# Return: {"job_id": str, "status": "pending"} immediately.
#
# @app.post("/render/{job_id}")
# def render(job_id: str, background_tasks: BackgroundTasks) -> dict:
#     jobs[job_id] = "pending"
#     background_tasks.add_task(_run_remotion_render, job_id)
#     return {"job_id": job_id, "status": "pending"}
#
#
# def _run_remotion_render(job_id: str) -> None:
#     # NOTE: subprocess.run blocks the calling thread. BackgroundTasks runs
#     # sync functions in a thread pool, so this is safe for MVP.
#     jobs[job_id] = "running"
#     result = subprocess.run(
#         [
#             "npx", "remotion", "render",
#             "src/index.ts",          # entry point
#             "LearnFlowSlide",        # composition id
#             f"out/{job_id}.mp4",     # output path (relative to render/)
#         ],
#         cwd="../render",
#         capture_output=True,
#     )
#     jobs[job_id] = "complete" if result.returncode == 0 else "error"


# ---------------------------------------------------------------------------
# GET /job/{job_id}
# ---------------------------------------------------------------------------
# Return: {"job_id": str, "status": "pending|running|complete|error|not_found"}
#
# @app.get("/job/{job_id}")
# def job_status(job_id: str) -> dict:
#     return {"job_id": job_id, "status": jobs.get(job_id, "not_found")}


# ---------------------------------------------------------------------------
# GET /quiz/{job_id}
# ---------------------------------------------------------------------------
# Return: {"job_id": str, "questions": list[dict]}
# Questions shape: [{"question": str, "choices": list[str], "answer_index": int}]
#
# @app.get("/quiz/{job_id}")
# def quiz(job_id: str) -> dict:
#     # TODO: generate 3-5 MCQ questions from the source PDF text via Claude API
#     return {"job_id": job_id, "questions": []}


# ---------------------------------------------------------------------------
# POST /eval
# ---------------------------------------------------------------------------
# Body: {"job_id": str}
# Return: {"narration_score": float, "full_source_score": float, "delta": float}
#
# @app.post("/eval")
# def eval_accuracy(body: dict) -> dict:
#     # TODO: call eval/eval.py compare_accuracy() with both context types
#     return {"narration_score": 0.0, "full_source_score": 0.0, "delta": 0.0}
```

- [ ] **Step 3: Install dependencies and verify the app starts**

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Expected: Uvicorn starts on `http://127.0.0.1:8000`. No import errors.

In a second terminal:

```bash
curl http://127.0.0.1:8000/health
```

Expected output: `{"status":"ok"}`

Stop the server with `Ctrl+C`.

- [ ] **Step 4: Commit**

```bash
git add backend/main.py backend/requirements.txt
git commit -m "feat: scaffold backend — FastAPI health check + commented route stubs"
```

---

## Task 2: Frontend scaffold

**Files:**

- Create: `frontend/index.html`
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`

**Interfaces:**

- Consumes: nothing from other tasks
- Produces: a Vite build that compiles without errors; `npm run dev` serves on `http://localhost:5173`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "learnflow-ai-frontend",
  "version": "0.0.1",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.6.3",
    "vite": "^6.0.3"
  }
}
```

- [ ] **Step 2: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Create `frontend/vite.config.ts`**

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
})
```

- [ ] **Step 4: Create `frontend/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>learnflow-ai</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Create `frontend/src/main.tsx`**

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

- [ ] **Step 6: Create `frontend/src/App.tsx`**

```tsx
export default function App() {
  return (
    <main>
      <h1>learnflow-ai</h1>
      <p>PDF → script → narrated video → quiz → eval</p>
      {/* TODO: upload → processing → quiz → results flow */}
    </main>
  )
}
```

- [ ] **Step 7: Install and verify the build**

```bash
cd frontend
npm install
npm run build
```

Expected: Vite outputs a `dist/` folder. TypeScript (`tsc`) reports zero errors. No warnings about missing types.

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold frontend — Vite + React + TypeScript placeholder"
```

---

## Task 3: Render scaffold

**Files:**

- Create: `render/package.json`
- Create: `render/tsconfig.json`
- Create: `render/remotion.config.ts`
- Create: `render/src/index.ts`
- Create: `render/src/Root.tsx`

**Interfaces:**

- Consumes: nothing from other tasks
- Produces: `npx remotion compositions src/index.ts` lists `LearnFlowSlide` (1920×1080, 30 fps, 150 frames)

- [ ] **Step 1: Create `render/package.json`**

```json
{
  "name": "learnflow-ai-render",
  "version": "0.0.1",
  "private": true,
  "scripts": {
    "studio": "npx remotion studio src/index.ts",
    "compositions": "npx remotion compositions src/index.ts",
    "render": "npx remotion render src/index.ts LearnFlowSlide out/video.mp4"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "remotion": "^4.0.0",
    "@remotion/cli": "^4.0.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "typescript": "^5.6.3"
  }
}
```

- [ ] **Step 2: Create `render/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "skipLibCheck": true,
    "noEmit": true
  },
  "include": ["src", "remotion.config.ts"]
}
```

- [ ] **Step 3: Create `render/remotion.config.ts`**

```ts
import { Config } from "@remotion/cli/config";

Config.setConcurrency(1);
```

- [ ] **Step 4: Create `render/src/Root.tsx`**

```tsx
import { Composition } from 'remotion'

function LearnFlowSlide() {
  return (
    <div
      style={{
        background: '#1a1a2e',
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <h1 style={{ color: '#ffffff', fontFamily: 'sans-serif' }}>
        Slide Title
      </h1>
    </div>
  )
}

export function Root() {
  return (
    <Composition
      id="LearnFlowSlide"
      component={LearnFlowSlide}
      durationInFrames={150}
      fps={30}
      width={1920}
      height={1080}
    />
  )
}
```

- [ ] **Step 5: Create `render/src/index.ts`**

```ts
import { registerRoot } from 'remotion'
import { Root } from './Root'

registerRoot(Root)
```

- [ ] **Step 6: Install and verify compositions are discovered**

```bash
cd render
npm install
npm run compositions
```

Expected output includes:

```
LearnFlowSlide  1920x1080  30fps  150 frames (5.00s)
```

No TypeScript or import errors.

- [ ] **Step 7: Commit**

```bash
git add render/
git commit -m "feat: scaffold render — Remotion TypeScript project with LearnFlowSlide composition"
```

---

## Task 4: Eval scaffold

**Files:**

- Create: `eval/eval.py`
- Create: `eval/results/.gitkeep`

**Interfaces:**

- Consumes: nothing from other tasks
- Produces: `python eval.py` exits 0 with no output; two importable stub functions

- [ ] **Step 1: Create `eval/results/.gitkeep`**

Create an empty file at `eval/results/.gitkeep` (no content needed — its presence tracks the directory in git).

- [ ] **Step 2: Create `eval/eval.py`**

```python
def run_quiz_with_context(context: str, quiz: list[dict]) -> dict:
    """Run quiz questions against an LLM given the provided context.

    Args:
        context: The text context to provide to the LLM (narration transcript
                 or full source PDF text).
        quiz: List of question dicts, each with keys:
              "question" (str), "choices" (list[str]), "answer_index" (int).

    Returns:
        Dict with keys "answers" (list[int]) and "score" (float 0.0–1.0).
    """
    ...


def compare_accuracy(narration_result: dict, full_source_result: dict) -> dict:
    """Compare quiz accuracy between narration-only and full-source contexts.

    Args:
        narration_result: Output of run_quiz_with_context() using narration text.
        full_source_result: Output of run_quiz_with_context() using full PDF text.

    Returns:
        Dict with keys "narration_score" (float), "full_source_score" (float),
        "delta" (float, full_source_score - narration_score).
    """
    ...


if __name__ == "__main__":
    pass
```

- [ ] **Step 3: Verify the script runs cleanly**

```bash
cd eval
python eval.py
```

Expected: no output, exit code 0.

- [ ] **Step 4: Commit**

```bash
git add eval/eval.py eval/results/.gitkeep
git commit -m "feat: scaffold eval — stub functions and empty results directory"
```

---

## Task 5: README and .gitignore

**Files:**

- Modify: `README.md`
- Modify: `.gitignore`

**Interfaces:**

- Consumes: nothing from other tasks
- Produces: a README that explains the project to a first-time visitor; a .gitignore that keeps the repo clean of build artifacts

- [ ] **Step 1: Replace `README.md` with the full skeleton**

Write this as the complete contents of `README.md`:

````markdown
# learnflow-ai

Turn any PDF into a short explainer video with an auto-generated comprehension quiz, then automatically benchmark how well the narration alone captures the source material.

## Architecture

```text
PDF → FastAPI → Claude API → ElevenLabs TTS → Remotion → video + quiz → eval
```

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python / FastAPI |
| PDF parsing | pdfplumber |
| Script generation | Claude API (Anthropic) |
| TTS | ElevenLabs |
| Video rendering | Remotion (React / TypeScript) |
| Frontend | Vite + React + TypeScript |
| Eval | Python (custom script) |

## MVP Scope

**v1 includes:**

- PDF input only
- Programmatic slide layouts (no AI-generated images)
- Single TTS voice (ElevenLabs)
- Static slides with crossfades (no animation)
- 3–5 question multiple-choice quiz

**Out of scope for v1:**

- Multiple input formats
- Animated diagrams
- Multi-language support
- Voice selection UI
- User accounts

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Render

```bash
cd render
npm install
npx remotion studio src/index.ts
```

### Eval

```bash
cd eval
python eval.py
```
````

- [ ] **Step 2: Append to `.gitignore`**

Add the following block at the end of the existing `.gitignore`:

```text
# JS/Node
node_modules/

# Remotion render output
render/out/

# Backend uploads and generated media
backend/uploads/
*.mp4
*.mp3
*.wav
```

- [ ] **Step 3: Verify .gitignore coverage**

```bash
git check-ignore -v frontend/node_modules render/out/video.mp4 backend/uploads/test.pdf
```

Expected: each path is reported as ignored. If any are not reported, confirm the `.gitignore` append landed correctly.

- [ ] **Step 4: Commit**

```bash
git add README.md .gitignore
git commit -m "docs: update README skeleton and extend .gitignore for JS and media artifacts"
```
