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

Requires `ANTHROPIC_API_KEY` and `ELEVENLABS_API_KEY` to be set as environment variables (see `backend/.env.example`).

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

## Known Limitations

- **Formula visual type is temporarily disabled.** Slides now render as one of `bullets`, `curve_plot`, `bar_chart`, or `diagram` — the fifth planned template, `formula` (a typeset equation with animated leader-lines annotating each part), is implemented end-to-end (schema, validation, and the Remotion component) but disabled at the prompt level after three separate fix attempts still left its annotation labels mispositioned in real renders. Content that would have used `formula` now falls back to `bullets`. See the comment above `_VISUAL_MODELS` in `backend/script_generator.py` for how to re-enable it once the positioning bug is actually fixed.
