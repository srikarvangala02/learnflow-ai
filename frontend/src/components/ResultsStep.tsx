import { cn } from '@/lib/utils'
import type { Question, EvalResult, EvalQuestionResult, FocusArea } from '@/lib/api'
import { VideoPlayer } from './VideoPlayer'

interface Props {
  questions: Question[]
  userAnswers: string[]
  evalResult: EvalResult
  renderJobId: string | null
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

export function ResultsStep({ questions, userAnswers, evalResult, renderJobId }: Props) {
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

      {/* Video */}
      <VideoPlayer renderJobId={renderJobId} />

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

      {/* Focus Areas */}
      {evalResult.focus_areas && evalResult.focus_areas.length > 0 && (
        <div className="flex flex-col gap-3">
          <h3 className="text-xs uppercase tracking-widest text-text-secondary">Focus Areas</h3>
          {evalResult.focus_areas.map((area: FocusArea, i: number) => (
            <div key={i} className="bg-surface border border-border rounded-xl p-4 flex flex-col gap-2">
              <span className="inline-block self-start text-xs font-semibold uppercase tracking-widest px-2 py-0.5 rounded-full bg-accent/20 text-accent">
                {area.topic}
              </span>
              <p className="text-sm text-text-secondary leading-relaxed">{area.explanation}</p>
            </div>
          ))}
        </div>
      )}

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
