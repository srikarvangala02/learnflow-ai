# learnflow-ai — Scaffold Design

**Date:** 2026-08-28
**Scope:** Initial project scaffold (v1 MVP structure only — no end-to-end functionality)

---

## 1. Project Overview

learnflow-ai is a pipeline that takes a PDF (paper or lecture notes) and produces:

1. A structured narration script via the Claude API
2. A narrated video of programmatic slides via Remotion + ElevenLabs TTS
3. A multiple-choice comprehension quiz generated from the source text
4. An automated eval comparing quiz accuracy under two contexts: narration-only vs. full-source

---

## 2. MVP Scope

**In scope for v1:**

- PDF input only
- No AI-generated images — programmatic slide layouts only
- Single TTS voice (ElevenLabs)
- Static slides with crossfades (no animation)
- 3–5 question multiple-choice quiz

**Out of scope for v1:**

- Multiple input formats
- Animated diagrams
- Multi-language support
- Voice selection UI
- User accounts

---

## 3. Folder Structure

```text
learnflow-ai/
├── backend/
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── src/
│       ├── main.tsx
│       └── App.tsx
├── render/
│   ├── remotion.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── src/
│       ├── index.ts
│       └── Root.tsx
├── eval/
│   ├── eval.py
│   └── results/
│       └── .gitkeep
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-08-28-learnflow-ai-scaffold-design.md
├── README.md
└── .gitignore
```

---

## 4. Backend (`backend/`)

### 4a. `main.py`

- FastAPI app instance
- `GET /health` — returns `{"status": "ok"}`
- In-memory `jobs: dict` store keyed by job ID
- Commented route stubs:
  - `POST /upload` — accept PDF, store to `uploads/`, return `file_id`
  - `POST /generate/{file_id}` — call Claude API to produce script JSON, return `job_id`
  - `POST /render/{job_id}` — enqueue background task; task runs `subprocess.run(["npx", "remotion", "render", ...])` inside the background task; returns `job_id` immediately
  - `GET /job/{job_id}` — poll status: `pending | running | complete | error`
  - `GET /quiz/{job_id}` — return generated quiz questions
  - `POST /eval` — run accuracy eval and return comparison result

### 4b. `requirements.txt`

```text
fastapi
uvicorn[standard]
anthropic
elevenlabs
pdfplumber
python-multipart
```

### 4c. Key Decisions

- Render is triggered as a subprocess (`npx remotion render`) from inside a FastAPI `BackgroundTasks` callback — no separate render server for MVP.
- Job state is in-memory only (no DB) — acceptable for single-session MVP demo.

---

## 5. Frontend (`frontend/`)

### 5a. Language

TypeScript (Vite + React template)

### 5b. `package.json` Dependencies

- `react`, `react-dom`
- Dev: `vite`, `@vitejs/plugin-react`, `typescript`, `@types/react`, `@types/react-dom`

### 5c. `src/App.tsx`

Single placeholder component: renders the app name, a one-line pipeline description, and a `// TODO: upload → processing → quiz → results flow` comment. Sufficient to confirm `vite build` succeeds.

### 5d. `src/main.tsx`

Standard Vite React entry: mounts `<App />` into `#root`.

---

## 6. Render (`render/`)

### 6a. Language

TypeScript (Remotion default)

### 6b. `package.json` Dependencies

- `remotion`, `@remotion/cli`, `react`, `react-dom`
- Dev: `typescript`, `@types/react`, `@types/react-dom`

### 6c. `src/Root.tsx`

Registers one `<Composition>` named `"LearnFlowSlide"` with:

- `durationInFrames`: 150 (5 s at 30 fps — placeholder)
- `fps`: 30
- `width`: 1920, `height`: 1080
- Component: inline placeholder `<div>` with slide title text

### 6d. `src/index.ts`

Calls `registerRoot(Root)` — the Remotion CLI entry point that discovers compositions.

### 6e. `remotion.config.ts`

Minimal config pointing entry to `src/index.ts`.

---

## 7. Eval (`eval/`)

### 7a. `eval.py`

Two empty stub functions:

```python
def run_quiz_with_context(context: str, quiz: list[dict]) -> dict:
    """Run quiz questions against an LLM given the provided context."""
    ...

def compare_accuracy(narration_result: dict, full_source_result: dict) -> dict:
    """Compare quiz accuracy between narration-only and full-source contexts."""
    ...

if __name__ == "__main__":
    pass
```

### 7b. `results/`

Empty directory tracked via `.gitkeep`.

---

## 8. README Structure

1. **Project pitch** — 2-sentence hook describing what learnflow-ai does
2. **Architecture overview** — text flowchart: `PDF → FastAPI → Claude API → ElevenLabs TTS → Remotion → video + quiz → eval`
3. **Tech stack** — table with columns: Layer / Technology
4. **MVP scope** — v1 in-scope and out-of-scope bullet lists
5. **Setup** — placeholder `## Setup` section with sub-headers: Backend, Frontend, Render, Eval

---

## 9. `.gitignore` Additions

```text
# JS/Node
node_modules/

# Render output
render/out/

# Uploads and generated media
backend/uploads/
*.mp4
*.mp3
*.wav
```

Note: `.env` is already covered by the existing gitignore.

---

## 10. What This Scaffold Does NOT Include

- No end-to-end wired logic (all routes are stubs)
- No database or persistent job store
- No Docker / docker-compose
- No CI configuration
- No authentication
- No actual Claude or ElevenLabs API calls
