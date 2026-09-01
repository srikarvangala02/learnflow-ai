# Frontend Wiring Design

**Date:** 2026-09-01
**Scope:** Wire the React frontend to the FastAPI backend. Implement a five-step UI flow: upload → generating → quiz → evaluating → results. Install Tailwind CSS, shadcn/ui, and react-dropzone.

---

## 1. Goal

Replace the placeholder `App.tsx` with a complete, polished single-page flow that takes a user from PDF upload to a quiz and a side-by-side eval comparison — all without a page refresh.

---

## 2. Tech Stack

- **Vite + React 18 + TypeScript** (already in place)
- **Tailwind CSS v3** — utility styling
- **shadcn/ui** — Card, Button, Badge, Progress components (dark theme)
- **react-dropzone** — drag-and-drop PDF upload
- **Inter** (Google Fonts) — primary typeface

---

## 3. Design Tokens

All tokens live in `tailwind.config.js` under `theme.extend.colors` and are mirrored as CSS custom properties in `index.css`.

| Token | Value | Role |
|---|---|---|
| `navy` | `#1a1a2e` | Page background (matches Remotion slides) |
| `surface` | `#16213e` | Card / panel background |
| `border` | `#0f3460` | Card borders, dividers |
| `accent` | `#7c3aed` | Primary CTA (violet) |
| `accent-hover` | `#6d28d9` | Hover state for accent |
| `text-primary` | `#e0e0ff` | Headings (matches slide title color) |
| `text-secondary` | `#c0c0e0` | Body / captions (matches slide bullet color) |
| `success` | `#22c55e` | Correct answers, high scores |
| `error` | `#ef4444` | Wrong answers, low scores |

Typography: Inter loaded via `<link>` in `index.html`. Headings: `font-semibold tracking-tight`. Step labels: `text-xs uppercase tracking-widest text-secondary`. Body: `text-sm leading-relaxed`.

---

## 4. File Structure

```
frontend/src/
  App.tsx                  — step state machine, renders active step component
  lib/
    api.ts                 — typed fetch wrappers for all backend calls
  components/
    UploadStep.tsx          — react-dropzone drop zone
    ProcessingStep.tsx      — spinner + polling
    QuizStep.tsx            — one question at a time
    ResultsStep.tsx         — scores + breakdown table
```

---

## 5. State Machine

`App.tsx` holds a single `step` state with a discriminated union:

```ts
type AppState =
  | { step: 'upload' }
  | { step: 'generating'; jobId: string }
  | { step: 'quiz'; jobId: string; questions: Question[] }
  | { step: 'evaluating'; jobId: string; questions: Question[]; userAnswers: string[] }
  | { step: 'results'; jobId: string; userAnswers: string[]; evalResult: EvalResult }
```

Transitions are pure: each child component calls a single `onComplete(payload)` prop to advance the step. No component reaches back into the parent's state.

---

## 6. API Layer (`lib/api.ts`)

All functions use `fetch` against `http://localhost:8000`. No external HTTP library.

```ts
const BASE = 'http://localhost:8000'

export type Question = {
  question: string
  options: string[]   // ["A. ...", "B. ...", "C. ...", "D. ..."]
  answer: string      // "A" | "B" | "C" | "D"
}

export type Job = {
  job_id: string
  status: 'pending' | 'running' | 'complete' | 'error'
  result: Record<string, unknown> | null
  error: string | null
}

export type QuizResponse = {
  job_id: string
  questions: Question[]
}

export type EvalQuestionResult = {
  question: string
  correct_answer: string
  narration_answer: string
  narration_correct: boolean
  full_source_answer: string
  full_source_correct: boolean
}

export type EvalResult = {
  job_id: string
  narration_score: number
  full_source_score: number
  total_questions: number
  questions: EvalQuestionResult[]
}

export async function uploadPdf(file: File): Promise<{ file_id: string }>
export async function startGenerate(fileId: string): Promise<{ job_id: string }>
export async function pollJob(jobId: string): Promise<Job>
export async function getQuiz(jobId: string): Promise<QuizResponse>
export async function runEval(jobId: string, questions: Question[]): Promise<EvalResult>
```

All functions throw on non-2xx responses.

---

## 7. Component Specs

### 7a. `UploadStep`

Props: `onComplete(fileId: string, jobId: string): void`

- Centered layout, max-width `480px`.
- react-dropzone accepts `application/pdf` only; rejects other types with an inline error message.
- Drop zone: dashed `border-2 border-border` rounded-xl, 200px tall, with an upload icon (lucide-react `UploadCloud`), primary text "Drop your PDF here", secondary text "or click to browse".
- On drop: disable the drop zone, show a loading spinner inside it while calling `uploadPdf` then `startGenerate` sequentially. On success, calls `onComplete(fileId, jobId)`.
- Error state: red border + inline message, re-enables drop zone.

### 7b. `ProcessingStep`

Props: `jobId: string; onComplete(questions: Question[]): void; onError(message: string): void`

- Full-height centered layout.
- Animated pulsing ring (CSS `animate-ping` outer ring + solid inner circle), accent violet color.
- Heading: "Analyzing your document…"
- Sub-label (all-caps, text-secondary): step label e.g. "GENERATING SCRIPT"
- Polls `pollJob(jobId)` every 3 s using `setInterval`, clears on unmount.
- On `status === 'complete'`: calls `getQuiz(jobId)` then `onComplete(questions)`.
- On `status === 'error'`: calls `onError(job.error ?? 'Unknown error')`.

### 7c. `QuizStep`

Props: `questions: Question[]; onComplete(userAnswers: string[]): void`

- Progress bar at top: shadcn/ui `Progress`, shows current question index / total.
- Question counter: "Question 2 of 5" in text-secondary.
- Question text: large `text-xl font-semibold text-primary`, `max-w-2xl`.
- Options: four full-width `<button>` cards, each showing the option text. Selected option gets `border-accent bg-accent/10`. Unselected: `border-border bg-surface`.
- "Next" button (shadcn `Button`, accent fill) advances; disabled until an option is selected.
- On the last question, button label changes to "See Results".
- Slide transition: simple fade (CSS `opacity` transition) between questions.
- `onComplete` called with array of selected letters (e.g. `["A", "B", "B", "C", "B"]`).

### 7d. `ResultsStep`

Props: `questions: Question[]; userAnswers: string[]; evalResult: EvalResult`

Layout: stacked sections, max-width `720px`, centered.

**Section 1 — Score cards** (three cards in a row on desktop, stacked on mobile):

1. **Your Score** — large number `X / N`, colored green if ≥ 80%, yellow if ≥ 60%, red otherwise.
2. **Narration Claude** — score + caption: *"Claude answered using only the slide narration — the same condensed text a viewer would hear."*
3. **Full-Source Claude** — score + caption: *"Claude answered using the complete PDF — the upper bound of what the material can support."*

**Section 2 — Question breakdown** (below the cards):

- Each question as a collapsible row (open by default): question text, then a 3-column grid: "Correct", "You", "Claude (narration)", "Claude (full)". Each answer cell shows the letter + ✓ or ✗ icon colored green/red.

**Section 3 — Reset** (bottom):

- "Start over" ghost button that reloads the page (simplest reset).

---

## 8. Tailwind Config

```js
// tailwind.config.js
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: '#1a1a2e',
        surface: '#16213e',
        border: '#0f3460',
        accent: '#7c3aed',
        'accent-hover': '#6d28d9',
        'text-primary': '#e0e0ff',
        'text-secondary': '#c0c0e0',
        success: '#22c55e',
        error: '#ef4444',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
```

---

## 9. shadcn/ui Setup

Install via CLI: `npx shadcn@latest init` with `dark` base color and `slate` as the base, then override the CSS variables in `globals.css` to match the navy palette.

Components used: `Button`, `Card`, `CardContent`, `CardHeader`, `Progress`, `Badge`.

---

## 10. Dependencies to Install

```
npm install tailwindcss postcss autoprefixer  (dev)
npm install react-dropzone
npm install lucide-react
npx shadcn@latest init
npx shadcn@latest add button card progress badge
```

---

## 11. Out of Scope

- Authentication
- Persisting jobs across page reloads (in-memory jobs only)
- Mobile-specific gestures beyond CSS responsiveness
- Routing / URL state
- Error recovery beyond inline messages and re-enabling the drop zone
