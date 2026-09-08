import { useEffect, useState } from 'react'
import { pollRenderJob, getRenderVideoUrl } from '@/lib/api'

interface Props {
  renderJobId: string | null
}

type VideoState =
  | { status: 'idle' }
  | { status: 'polling' }
  | { status: 'ready'; url: string }
  | { status: 'error' }

export function VideoPlayer({ renderJobId }: Props) {
  const [video, setVideo] = useState<VideoState>(
    renderJobId ? { status: 'polling' } : { status: 'idle' },
  )

  useEffect(() => {
    if (!renderJobId) return

    let cancelled = false

    async function poll() {
      while (!cancelled) {
        try {
          const job = await pollRenderJob(renderJobId!)
          if (job.status === 'complete') {
            if (!cancelled) setVideo({ status: 'ready', url: getRenderVideoUrl(renderJobId!) })
            return
          }
          if (job.status === 'error') {
            if (!cancelled) setVideo({ status: 'error' })
            return
          }
        } catch {
          if (!cancelled) setVideo({ status: 'error' })
          return
        }
        await new Promise((r) => setTimeout(r, 5000))
      }
    }

    poll()
    return () => {
      cancelled = true
    }
  }, [renderJobId])

  if (video.status === 'idle') return null

  if (video.status === 'polling') {
    return (
      <div className="bg-surface border border-border rounded-xl p-4 flex items-center gap-3">
        <svg
          className="animate-spin h-4 w-4 text-text-secondary shrink-0"
          viewBox="0 0 24 24"
          fill="none"
        >
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
        </svg>
        <span className="text-sm text-text-secondary">Generating video…</span>
      </div>
    )
  }

  if (video.status === 'error') {
    return (
      <div className="bg-surface border border-border rounded-xl p-4">
        <span className="text-sm text-text-secondary">Video unavailable</span>
      </div>
    )
  }

  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <video src={video.url} controls className="w-full" />
    </div>
  )
}
