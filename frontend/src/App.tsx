import { useState } from 'react'
import type { Question, EvalResult } from './lib/api'
import { startRender } from './lib/api'
import { UploadStep } from './components/UploadStep'
import { ProcessingStep } from './components/ProcessingStep'
import { QuizStep } from './components/QuizStep'
import { ResultsStep } from './components/ResultsStep'

type AppState =
  | { step: 'upload'; error?: string }
  | { step: 'generating'; jobId: string }
  | { step: 'quiz'; jobId: string; questions: Question[]; renderJobId: string | null }
  | { step: 'results'; questions: Question[]; userAnswers: string[]; evalResult: EvalResult; renderJobId: string | null }

export default function App() {
  const [state, setState] = useState<AppState>({ step: 'upload' })

  return (
    <div className="min-h-screen bg-navy font-sans flex flex-col items-center justify-center p-6">
      <header className="mb-10 text-center">
        <p className="text-xs uppercase tracking-widest text-text-secondary mb-2">learnflow-ai</p>
        <h1 className="text-3xl font-semibold tracking-tight text-text-primary">PDF → Quiz → Eval</h1>
      </header>

      {state.step === 'upload' && (
        <>
          <UploadStep
            onComplete={(jobId) => setState({ step: 'generating', jobId })}
          />
          {state.error && (
            <p className="mt-4 text-sm text-error text-center max-w-md">{state.error}</p>
          )}
        </>
      )}

      {state.step === 'generating' && (
        <ProcessingStep
          jobId={state.jobId}
          onComplete={async (questions) => {
            let renderJobId: string | null = null
            try {
              const { job_id } = await startRender(state.jobId)
              renderJobId = job_id
            } catch {
              // non-fatal — video section will show "Video unavailable"
            }
            setState({ step: 'quiz', jobId: state.jobId, questions, renderJobId })
          }}
          onError={(message) => setState({ step: 'upload', error: message })}
        />
      )}

      {state.step === 'quiz' && (
        <QuizStep
          jobId={state.jobId}
          questions={state.questions}
          onComplete={(userAnswers, evalResult) =>
            setState({
              step: 'results',
              questions: state.questions,
              userAnswers,
              evalResult,
              renderJobId: state.renderJobId,
            })
          }
        />
      )}

      {state.step === 'results' && (
        <ResultsStep
          questions={state.questions}
          userAnswers={state.userAnswers}
          evalResult={state.evalResult}
          renderJobId={state.renderJobId}
        />
      )}
    </div>
  )
}
