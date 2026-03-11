'use client'

import type { ReactNode } from 'react'
import { useEffect, useId, useState } from 'react'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'

type DialogTone = 'default' | 'destructive'

export interface ConfirmActionDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: ReactNode
  description?: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  tone?: DialogTone
  isPending?: boolean
  disableConfirm?: boolean
  rememberChoiceKey?: string
  rememberChoiceLabel?: string
  children?: ReactNode
  onConfirm: () => void | Promise<void>
}

/**
 * Shared confirmation dialog so destructive flows feel consistent everywhere.
 */
export function ConfirmActionDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = 'Continue',
  cancelLabel = 'Cancel',
  tone = 'destructive',
  isPending = false,
  disableConfirm = false,
  rememberChoiceKey,
  rememberChoiceLabel = "Don't ask me again",
  children,
  onConfirm,
}: ConfirmActionDialogProps) {
  const [rememberChoice, setRememberChoice] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const checkboxId = useId()

  useEffect(() => {
    if (!open) {
      setRememberChoice(false)
      setIsSubmitting(false)
      setSubmitError(null)
    }
  }, [open])

  const handleConfirm = async () => {
    setIsSubmitting(true)
    setSubmitError(null)
    try {
      await onConfirm()
      if (
        rememberChoice &&
        rememberChoiceKey &&
        typeof window !== 'undefined'
      ) {
        localStorage.setItem(rememberChoiceKey, 'true')
      }
      onOpenChange(false)
    } catch (error) {
      setSubmitError(
        error instanceof Error ? error.message : 'Unable to complete that action.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="confirm-action-dialog">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        {submitError ? (
          <LoadErrorState
            title="Action failed."
            detail={submitError}
            className="p-4"
          />
        ) : null}
        {children}
        {rememberChoiceKey && (
          <div className="flex items-center space-x-2 rounded-md border border-border/50 bg-surface/60 p-3">
            <Checkbox
              id={checkboxId}
              checked={rememberChoice}
              onCheckedChange={(checked) => setRememberChoice(Boolean(checked))}
            />
            <Label
              htmlFor={checkboxId}
              className="cursor-pointer text-sm text-text-muted"
            >
              {rememberChoiceLabel}
            </Label>
          </div>
        )}
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isPending || isSubmitting}
          >
            {cancelLabel}
          </Button>
          <Button
            type="button"
            variant={tone === 'destructive' ? 'destructive' : 'default'}
            onClick={handleConfirm}
            disabled={disableConfirm || isPending || isSubmitting}
          >
            {isPending || isSubmitting ? 'Working...' : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
