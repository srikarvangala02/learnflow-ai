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
        const evalResult = await runEval(jobId, questions, nextAnswers)
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
