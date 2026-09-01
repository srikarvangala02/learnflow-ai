# Frontend Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the React frontend to the FastAPI backend — upload → generating → quiz → results — with a polished dark-navy UI.

**Architecture:** Single-page step machine in `App.tsx` with a discriminated-union state; each step component calls `onComplete(payload)` to advance. No router, no external state library. shadcn-style UI primitives built manually from Tailwind for reliability. QuizStep handles the eval API call internally and calls `onComplete(userAnswers, evalResult)` when done.

**Tech Stack:** Vite + React 18 + TypeScript, Tailwind CSS v3, react-dropzone, lucide-react, clsx, tailwind-merge.

**Spec:** `docs/superpowers/specs/2026-09-01-frontend-wiring-design.md`

## Global Constraints

- Tailwind CSS v3 (pin `tailwindcss@^3` — do NOT install v4).
- No external state library (useState only).
- API base URL from `import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'` — never hardcode.
- `@/` path alias maps to `./src/` — use it for all cross-directory imports.
- All color classes use the custom tokens: `navy`, `surface`, `border`, `accent`, `accent-hover`, `text-primary`, `text-secondary`, `success`, `error`.
- Backend must have CORS middleware permitting `http://localhost:5173`.
- Inter font loaded from Google Fonts in `index.html`.
- State machine has four steps only: `upload | generating | quiz | results`. There is no separate `evaluating` step — QuizStep handles the eval call internally.

---

### Task 1: Tooling — Tailwind, UI primitives, CORS, font

**Files:**
- Modify: `frontend/package.json` (via npm install)
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Modify: `frontend/vite.config.ts` (path alias)
- Modify: `frontend/tsconfig.json` (path alias)
- Modify: `frontend/src/index.css` (Tailwind directives + CSS resets)
- Modify: `frontend/index.html` (Inter font link)
- Create: `frontend/.env.example`
- Create: `frontend/src/lib/utils.ts`
- Create: `frontend/src/components/ui/button.tsx`
- Create: `frontend/src/components/ui/progress.tsx`
- Create: `frontend/src/components/ui/badge.tsx`
- Modify: `backend/main.py` (CORS middleware)

**Interfaces:**
- Produces: `cn()` utility, `Button`, `Progress`, `Badge` components — all imported via `@/lib/utils` and `@/components/ui/*` in later tasks.

- [ ] **Step 1: Install frontend dependencies**

Run from `frontend/`:
```bash
npm install -D tailwindcss@^3 postcss autoprefixer @types/node
npm install clsx tailwind-merge react-dropzone lucide-react
```

Expected: no errors. `package.json` now lists these dependencies.

- [ ] **Step 2: Initialise Tailwind**

Run from `frontend/`:
```bash
npx tailwindcss init -p
```

This creates `tailwind.config.js` and `postcss.config.js`. Replace `tailwind.config.js` entirely:

```js
// frontend/tailwind.config.js
/** @type {import('tailwindcss').Config} */
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

Verify `postcss.config.js` exists (npx created it). Its contents should be:
```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

- [ ] **Step 3: Configure Vite path alias**

Replace `frontend/vite.config.ts`:
```ts
import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
```

- [ ] **Step 4: Configure TypeScript path alias**

Read `frontend/tsconfig.json`. Add `baseUrl` and `paths` inside `compilerOptions`:
```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```
Keep all existing compilerOptions, just add these two keys.

- [ ] **Step 5: Set up index.css**

Replace `frontend/src/index.css` entirely:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  background-color: #1a1a2e;
  color: #e0e0ff;
}
```

- [ ] **Step 6: Add Inter font to index.html**

Add this `<link>` inside `<head>` in `frontend/index.html`, before the closing `</head>`:
```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet" />
```

- [ ] **Step 7: Create .env.example**

Create `frontend/.env.example`:
```
# URL of the learnflow-ai FastAPI backend.
# In development this defaults to http://localhost:8000 when not set.
VITE_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 8: Create src/lib/utils.ts**

Create `frontend/src/lib/utils.ts`:
```ts
import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

- [ ] **Step 9: Create UI primitive — Button**

Create `frontend/src/components/ui/button.tsx`:
```tsx
import { cn } from '@/lib/utils'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'ghost'
}

export function Button({ className, variant = 'default', ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-medium transition-colors',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        variant === 'default' && 'bg-accent text-white hover:bg-accent-hover',
        variant === 'ghost' && 'text-text-secondary hover:text-text-primary underline underline-offset-4',
        className,
      )}
      {...props}
    />
  )
}
```

- [ ] **Step 10: Create UI primitive — Progress**

Create `frontend/src/components/ui/progress.tsx`:
```tsx
import { cn } from '@/lib/utils'

interface ProgressProps {
  value: number
  className?: string
}

export function Progress({ value, className }: ProgressProps) {
  return (
    <div className={cn('w-full h-1 rounded-full bg-surface overflow-hidden', className)}>
      <div
        className="h-full bg-accent transition-all duration-300 rounded-full"
        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      />
    </div>
  )
}
```

- [ ] **Step 11: Create UI primitive — Badge**

Create `frontend/src/components/ui/badge.tsx`:
```tsx
import { cn } from '@/lib/utils'

interface BadgeProps {
  children: React.ReactNode
  className?: string
}

export function Badge({ children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md border border-border px-2.5 py-0.5 text-xs font-medium text-text-secondary',
        className,
      )}
    >
      {children}
    </span>
  )
}
```

- [ ] **Step 12: Add CORS middleware to backend**

Open `backend/main.py`. Add `CORSMiddleware` import and setup immediately after `app = FastAPI(...)`:

```python
from fastapi.middleware.cors import CORSMiddleware

# Add after: app = FastAPI(title="learnflow-ai")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 13: Verify tooling**

In `frontend/src/App.tsx`, temporarily replace the content with:
```tsx
import { Button } from '@/components/ui/button'

export default function App() {
  return (
    <div className="min-h-screen bg-navy flex items-center justify-center">
      <div className="text-center">
        <p className="text-xs uppercase tracking-widest text-text-secondary mb-4">learnflow-ai</p>
        <h1 className="text-3xl font-semibold text-text-primary mb-8">PDF → Quiz → Eval</h1>
        <Button>Get started</Button>
      </div>
    </div>
  )
}
```

Run from `frontend/`:
```bash
npm run dev
```

Expected: browser opens, navy background, Inter font, violet button visible. No console errors.

Also run:
```bash
npm run build
```
Expected: build succeeds with no TypeScript errors.

- [ ] **Step 14: Commit**

```bash
git add frontend/ backend/main.py
git commit -m "feat: set up Tailwind, UI primitives, CORS, and Inter font"
```

---

### Task 2: API layer (`src/lib/api.ts`)

**Files:**
- Create: `frontend/src/lib/api.ts`

**Interfaces:**
- Produces: `Question`, `Job`, `QuizResponse`, `EvalQuestionResult`, `EvalResult` types + `uploadPdf`, `startGenerate`, `pollJob`, `getQuiz`, `runEval` functions — imported by all step components.

- [ ] **Step 1: Create api.ts**

Create `frontend/src/lib/api.ts`:
```ts
const BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

export type Question = {
  question: string
  options: string[]  // e.g. ["A. Set of outcomes", "B. A probability", ...]
  answer: string     // "A" | "B" | "C" | "D"
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

export function uploadPdf(file: File): Promise<{ file_id: string }> {
  const form = new FormData()
  form.append('file', file)
  return request('/upload', { method: 'POST', body: form })
}

export function startGenerate(fileId: string): Promise<{ job_id: string }> {
  return request(`/generate/${fileId}`, { method: 'POST' })
}

export function pollJob(jobId: string): Promise<Job> {
  return request(`/job/${jobId}`)
}

export function getQuiz(jobId: string): Promise<QuizResponse> {
  return request(`/quiz/${jobId}`)
}

export function runEval(jobId: string, questions: Question[]): Promise<EvalResult> {
  return request('/eval', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ job_id: jobId, questions }),
  })
}
```

- [ ] **Step 2: Verify TypeScript**

Run from `frontend/`:
```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: add typed API layer for all backend endpoints"
```

---

### Task 3: UploadStep component

**Files:**
- Create: `frontend/src/components/UploadStep.tsx`

**Interfaces:**
- Consumes: `uploadPdf`, `startGenerate` from `@/lib/api`
- Produces: `UploadStep` component with props `{ onComplete: (jobId: string) => void }`

- [ ] **Step 1: Create UploadStep.tsx**

Create `frontend/src/components/UploadStep.tsx`:
```tsx
import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { UploadCloud, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { uploadPdf, startGenerate } from '@/lib/api'

interface Props {
  onComplete: (jobId: string) => void
}

export function UploadStep({ onComplete }: Props) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onDrop = useCallback(async (accepted: File[], rejected: { errors: { message: string }[] }[]) => {
    if (rejected.length > 0) {
      setError('Only PDF files are accepted.')
      return
    }
    const file = accepted[0]
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const { file_id } = await uploadPdf(file)
      const { job_id } = await startGenerate(file_id)
      onComplete(job_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed. Please try again.')
      setLoading(false)
    }
  }, [onComplete])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    disabled: loading,
  })

  return (
    <div className="w-full max-w-md flex flex-col gap-3">
      <div
        {...getRootProps()}
        className={cn(
          'flex flex-col items-center justify-center gap-3 h-52 rounded-xl border-2 border-dashed',
          'transition-colors duration-200 outline-none',
          loading
            ? 'border-border opacity-60 cursor-not-allowed'
            : isDragActive
            ? 'border-accent bg-accent/5 cursor-copy'
            : 'border-border hover:border-accent/60 cursor-pointer',
          error && !loading && 'border-error',
        )}
      >
        <input {...getInputProps()} />
        {loading ? (
          <Loader2 className="h-8 w-8 text-accent animate-spin" />
        ) : (
          <UploadCloud className={cn('h-8 w-8', isDragActive ? 'text-accent' : 'text-text-secondary')} />
        )}
        <div className="text-center select-none">
          <p className="text-text-primary font-medium">
            {loading ? 'Uploading…' : isDragActive ? 'Drop it here' : 'Drop your PDF here'}
          </p>
          {!loading && (
            <p className="text-xs text-text-secondary mt-1">or click to browse</p>
          )}
        </div>
      </div>
      {error && (
        <p className="text-sm text-error text-center">{error}</p>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Wire temporarily into App.tsx for visual check**

Update `frontend/src/App.tsx`:
```tsx
import { UploadStep } from './components/UploadStep'

export default function App() {
  return (
    <div className="min-h-screen bg-navy flex flex-col items-center justify-center p-6">
      <header className="mb-10 text-center">
        <p className="text-xs uppercase tracking-widest text-text-secondary mb-2">learnflow-ai</p>
        <h1 className="text-3xl font-semibold tracking-tight text-text-primary">PDF → Quiz → Eval</h1>
      </header>
      <UploadStep onComplete={(jobId) => console.log('job_id:', jobId)} />
    </div>
  )
}
```

Run `npm run dev`. Expected: drop zone visible with icon, correct colors. Try dragging a non-PDF — expect error message. Drag a PDF with backend running — check console for `job_id`.

- [ ] **Step 3: Verify TypeScript**

```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/UploadStep.tsx frontend/src/App.tsx
git commit -m "feat: add UploadStep with react-dropzone"
```

---

### Task 4: ProcessingStep component

**Files:**
- Create: `frontend/src/components/ProcessingStep.tsx`

**Interfaces:**
- Consumes: `pollJob`, `getQuiz`, `Question` from `@/lib/api`
- Produces: `ProcessingStep` component with props `{ jobId: string; onComplete: (questions: Question[]) => void; onError: (message: string) => void }`

- [ ] **Step 1: Create ProcessingStep.tsx**

Create `frontend/src/components/ProcessingStep.tsx`:
```tsx
import { useEffect } from 'react'
import { pollJob, getQuiz } from '@/lib/api'
import type { Question } from '@/lib/api'

interface Props {
  jobId: string
  onComplete: (questions: Question[]) => void
  onError: (message: string) => void
}

export function ProcessingStep({ jobId, onComplete, onError }: Props) {
  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const job = await pollJob(jobId)
        if (job.status === 'complete') {
          clearInterval(id)
          const { questions } = await getQuiz(jobId)
          onComplete(questions)
        } else if (job.status === 'error') {
          clearInterval(id)
          onError(job.error ?? 'Script generation failed.')
        }
      } catch (err) {
        clearInterval(id)
        onError(err instanceof Error ? err.message : 'Connection error. Is the backend running?')
      }
    }, 3000)
    return () => clearInterval(id)
  }, [jobId, onComplete, onError])

  return (
    <div className="flex flex-col items-center gap-6">
      <div className="relative h-16 w-16">
        <div className="absolute inset-0 rounded-full bg-accent/20 animate-ping" />
        <div className="relative h-16 w-16 rounded-full bg-accent/40" />
      </div>
      <div className="text-center">
        <h2 className="text-xl font-semibold text-text-primary">Analyzing your document…</h2>
        <p className="text-xs uppercase tracking-widest text-text-secondary mt-2">Generating Script</p>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ProcessingStep.tsx
git commit -m "feat: add ProcessingStep with polling"
```

---

### Task 5: QuizStep component

**Files:**
- Create: `frontend/src/components/QuizStep.tsx`

**Interfaces:**
- Consumes: `runEval`, `Question`, `EvalResult` from `@/lib/api`; `Button` from `@/components/ui/button`; `Progress` from `@/components/ui/progress`
- Produces: `QuizStep` component with props `{ jobId: string; questions: Question[]; onComplete: (userAnswers: string[], evalResult: EvalResult) => void }`

- [ ] **Step 1: Create QuizStep.tsx**

Create `frontend/src/components/QuizStep.tsx`:
```tsx
import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { runEval } from '@/lib/api'
import type { Question, EvalResult } from '@/lib/api'

interface Props {
  jobId: string
  questions: Question[]
  onComplete: (userAnswers: string[], evalResult: EvalResult) => void
}

export function QuizStep({ jobId, questions, onComplete }: Props) {
  const [current, setCurrent] = useState(0)
  const [answers, setAnswers] = useState<string[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const q = questions[current]
  const isLast = current === questions.length - 1
  const progress = ((current + 1) / questions.length) * 100

  const handleNext = async () => {
    if (!selected) return
    const nextAnswers = [...answers, selected]

    if (isLast) {
      setSubmitting(true)
      setError(null)
      try {
        const evalResult = await runEval(jobId, questions)
        onComplete(nextAnswers, evalResult)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Evaluation failed. Please try again.')
        setSubmitting(false)
      }
    } else {
      setAnswers(nextAnswers)
      setSelected(null)
      setCurrent(c => c + 1)
    }
  }

  return (
    <div className="w-full max-w-2xl flex flex-col gap-6">
      {/* Progress */}
      <div className="flex flex-col gap-2">
        <div className="flex justify-between text-xs uppercase tracking-widest text-text-secondary">
          <span>Question {current + 1} of {questions.length}</span>
        </div>
        <Progress value={progress} />
      </div>

      {/* Question */}
      <h2 className="text-xl font-semibold text-text-primary leading-snug">{q.question}</h2>

      {/* Options */}
      <div className="flex flex-col gap-3">
        {q.options.map((opt) => {
          const letter = opt[0]
          const isSelected = selected === letter
          return (
            <button
              key={letter}
              onClick={() => !submitting && setSelected(letter)}
              disabled={submitting}
              className={cn(
                'w-full text-left px-5 py-4 rounded-xl border-2 transition-all duration-150 text-sm font-medium',
                isSelected
                  ? 'border-accent bg-accent/10 text-text-primary'
                  : 'border-border bg-surface text-text-primary hover:border-accent/50',
                submitting && 'opacity-60 cursor-not-allowed',
              )}
            >
              {opt}
            </button>
          )
        })}
      </div>

      {error && <p className="text-sm text-error text-center">{error}</p>}

      {/* Next / Submit */}
      <div className="flex justify-end">
        <Button
          onClick={handleNext}
          disabled={!selected || submitting}
          className="px-8"
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              Evaluating…
            </>
          ) : isLast ? (
            'See Results'
          ) : (
            'Next'
          )}
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/QuizStep.tsx
git commit -m "feat: add QuizStep with per-question navigation and eval trigger"
```

---

### Task 6: ResultsStep component

**Files:**
- Create: `frontend/src/components/ResultsStep.tsx`

**Interfaces:**
- Consumes: `Question`, `EvalResult`, `EvalQuestionResult` from `@/lib/api`
- Produces: `ResultsStep` component with props `{ questions: Question[]; userAnswers: string[]; evalResult: EvalResult }`

- [ ] **Step 1: Create ResultsStep.tsx**

Create `frontend/src/components/ResultsStep.tsx`:
```tsx
import { cn } from '@/lib/utils'
import type { Question, EvalResult, EvalQuestionResult } from '@/lib/api'

interface Props {
  questions: Question[]
  userAnswers: string[]
  evalResult: EvalResult
}

function scoreColor(score: number, total: number) {
  if (total === 0) return 'text-text-secondary'
  const pct = score / total
  if (pct >= 0.8) return 'text-success'
  if (pct >= 0.6) return 'text-yellow-400'
  return 'text-error'
}

function ScoreCard({
  label,
  score,
  total,
  caption,
}: {
  label: string
  score: number
  total: number
  caption?: string
}) {
  return (
    <div className="flex-1 min-w-0 bg-surface border border-border rounded-xl p-5 flex flex-col gap-2">
      <p className="text-xs uppercase tracking-widest text-text-secondary">{label}</p>
      <p className={cn('text-4xl font-semibold', scoreColor(score, total))}>
        {score}
        <span className="text-lg text-text-secondary font-normal"> / {total}</span>
      </p>
      {caption && (
        <p className="text-xs text-text-secondary leading-relaxed mt-1">{caption}</p>
      )}
    </div>
  )
}

function AnswerCell({ letter, correct }: { letter: string; correct: boolean }) {
  return (
    <span className={cn('font-medium', correct ? 'text-success' : 'text-error')}>
      {letter} {correct ? '✓' : '✗'}
    </span>
  )
}

function QuestionRow({
  eq,
  userAnswer,
  correctAnswer,
}: {
  eq: EvalQuestionResult
  userAnswer: string
  correctAnswer: string
}) {
  return (
    <div className="bg-surface border border-border rounded-xl p-4 flex flex-col gap-3">
      <p className="text-sm text-text-primary font-medium leading-snug">{eq.question}</p>
      <div className="grid grid-cols-4 gap-2 text-xs">
        <div>
          <p className="uppercase tracking-widest text-text-secondary mb-1">Correct</p>
          <span className="text-success font-medium">{eq.correct_answer}</span>
        </div>
        <div>
          <p className="uppercase tracking-widest text-text-secondary mb-1">You</p>
          <AnswerCell letter={userAnswer ?? '—'} correct={userAnswer === correctAnswer} />
        </div>
        <div>
          <p className="uppercase tracking-widest text-text-secondary mb-1">Narration</p>
          <AnswerCell letter={eq.narration_answer} correct={eq.narration_correct} />
        </div>
        <div>
          <p className="uppercase tracking-widest text-text-secondary mb-1">Full Source</p>
          <AnswerCell letter={eq.full_source_answer} correct={eq.full_source_correct} />
        </div>
      </div>
    </div>
  )
}

export function ResultsStep({ questions, userAnswers, evalResult }: Props) {
  const userScore = questions.reduce(
    (acc, q, i) => acc + (userAnswers[i] === q.answer ? 1 : 0),
    0,
  )
  const total = questions.length

  return (
    <div className="w-full max-w-2xl flex flex-col gap-8">
      <div className="text-center">
        <p className="text-xs uppercase tracking-widest text-text-secondary mb-2">Complete</p>
        <h2 className="text-2xl font-semibold text-text-primary">Results</h2>
      </div>

      {/* Score cards */}
      <div className="flex gap-4 flex-col sm:flex-row">
        <ScoreCard label="Your Score" score={userScore} total={total} />
        <ScoreCard
          label="Narration Claude"
          score={evalResult.narration_score}
          total={total}
          caption="Claude answered using only the slide narration — the same condensed text a viewer would hear."
        />
        <ScoreCard
          label="Full-Source Claude"
          score={evalResult.full_source_score}
          total={total}
          caption="Claude answered using the complete PDF — the upper bound of what the material can support."
        />
      </div>

      {/* Breakdown */}
      <div className="flex flex-col gap-3">
        <h3 className="text-xs uppercase tracking-widest text-text-secondary">Question Breakdown</h3>
        {evalResult.questions.map((eq, i) => (
          <QuestionRow
            key={i}
            eq={eq}
            userAnswer={userAnswers[i]}
            correctAnswer={eq.correct_answer}
          />
        ))}
      </div>

      {/* Reset */}
      <div className="flex justify-center pb-4">
        <button
          onClick={() => window.location.reload()}
          className="text-sm text-text-secondary underline underline-offset-4 hover:text-text-primary transition-colors"
        >
          Start over
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ResultsStep.tsx
git commit -m "feat: add ResultsStep with score cards and question breakdown"
```

---

### Task 7: App.tsx state machine + end-to-end test

**Files:**
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: all four step components, `Question` and `EvalResult` from `@/lib/api`

- [ ] **Step 1: Replace App.tsx with the state machine**

Replace `frontend/src/App.tsx` entirely:
```tsx
import { useState } from 'react'
import type { Question, EvalResult } from './lib/api'
import { UploadStep } from './components/UploadStep'
import { ProcessingStep } from './components/ProcessingStep'
import { QuizStep } from './components/QuizStep'
import { ResultsStep } from './components/ResultsStep'

type AppState =
  | { step: 'upload' }
  | { step: 'generating'; jobId: string }
  | { step: 'quiz'; jobId: string; questions: Question[] }
  | { step: 'results'; questions: Question[]; userAnswers: string[]; evalResult: EvalResult }

export default function App() {
  const [state, setState] = useState<AppState>({ step: 'upload' })

  return (
    <div className="min-h-screen bg-navy font-sans flex flex-col items-center justify-center p-6">
      <header className="mb-10 text-center">
        <p className="text-xs uppercase tracking-widest text-text-secondary mb-2">learnflow-ai</p>
        <h1 className="text-3xl font-semibold tracking-tight text-text-primary">PDF → Quiz → Eval</h1>
      </header>

      {state.step === 'upload' && (
        <UploadStep
          onComplete={(jobId) => setState({ step: 'generating', jobId })}
        />
      )}

      {state.step === 'generating' && (
        <ProcessingStep
          jobId={state.jobId}
          onComplete={(questions) =>
            setState({ step: 'quiz', jobId: state.jobId, questions })
          }
          onError={() => setState({ step: 'upload' })}
        />
      )}

      {state.step === 'quiz' && (
        <QuizStep
          jobId={state.jobId}
          questions={state.questions}
          onComplete={(userAnswers, evalResult) =>
            setState({ step: 'results', questions: state.questions, userAnswers, evalResult })
          }
        />
      )}

      {state.step === 'results' && (
        <ResultsStep
          questions={state.questions}
          userAnswers={state.userAnswers}
          evalResult={state.evalResult}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: End-to-end test**

Prerequisites:
- Backend running: `python -m uvicorn main:app --reload` (from `backend/` with venv active and `ANTHROPIC_API_KEY` set)
- Frontend running: `npm run dev` (from `frontend/`)

Manual flow:
1. Open `http://localhost:5173` — expect navy background, drop zone.
2. Drop a PDF — expect spinner briefly, then pulsing animation.
3. Wait ~30–60 s for generation — expect quiz appears with progress bar.
4. Answer all 5 questions — expect "See Results" on the last one.
5. Click "See Results" — expect ~30 s evaluating spinner on button, then results screen.
6. Verify: three score cards render with captions, breakdown table shows ✓/✗ for all columns.
7. Click "Start over" — expect page reloads back to upload step.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: wire App.tsx state machine — full upload → quiz → results flow"
```
