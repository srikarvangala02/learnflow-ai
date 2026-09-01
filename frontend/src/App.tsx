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
