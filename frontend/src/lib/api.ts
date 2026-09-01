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
