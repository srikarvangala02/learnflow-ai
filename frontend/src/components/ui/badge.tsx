import { cn } from '@/lib/utils'

interface BadgeProps {
  children: React.ReactNode
  className?: string
}

export function Badge({ children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md border border-border px-2.5 py-0.5 text-xs font-medium text-text-secondary',
        className,
      )}
    >
      {children}
    </span>
  )
}
