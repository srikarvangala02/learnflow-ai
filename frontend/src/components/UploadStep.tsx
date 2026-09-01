import { useCallback, useState } from 'react'
import { useDropzone, FileRejection } from 'react-dropzone'
import { UploadCloud, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { uploadPdf, startGenerate } from '@/lib/api'

interface Props {
  onComplete: (jobId: string) => void
}

export function UploadStep({ onComplete }: Props) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onDrop = useCallback(async (accepted: File[], rejected: FileRejection[]) => {
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
