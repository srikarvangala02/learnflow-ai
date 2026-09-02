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
