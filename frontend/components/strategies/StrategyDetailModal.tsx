'use client'

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { useStrategy } from '@/lib/hooks/useStrategies'
import { StrategyDetailModalContent } from './StrategyDetailModalContent'

interface StrategyDetailModalProps {
  strategyId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function StrategyDetailModal({
  strategyId,
  open,
  onOpenChange,
}: StrategyDetailModalProps) {
  const { data: strategy, isLoading } = useStrategy(strategyId)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto">
        {isLoading ? (
          <DialogHeader>
            <DialogTitle>Loading Strategy...</DialogTitle>
            <div className="space-y-4 pt-4">
              <Skeleton className="h-8 w-1/2" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-32 w-full" />
            </div>
          </DialogHeader>
        ) : strategy ? (
          <StrategyDetailModalContent strategy={strategy} />
        ) : (
          <DialogHeader>
            <DialogTitle>Strategy Not Found</DialogTitle>
            <p className="text-text-muted">
              The requested strategy could not be found.
            </p>
          </DialogHeader>
        )}
      </DialogContent>
    </Dialog>
  )
}
