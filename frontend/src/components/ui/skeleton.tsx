import { HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

/**
 * Placeholder animado para estados de loading.
 * Uso:   <Skeleton className="h-10 w-64" />
 */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('animate-pulse rounded-md bg-muted', className)}
      {...props}
    />
  )
}
