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
