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
