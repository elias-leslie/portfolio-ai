'use client'

import {
  type AccountType,
  getAccountNameError,
  normalizeAccountName,
} from '@/components/portfolio/portfolio-form-utils'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useCreateAccount } from '@/lib/hooks/usePortfolio'
import { useState } from 'react'
import { toast } from 'sonner'

interface AddAccountDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function AddAccountDialog({ open, onOpenChange }: AddAccountDialogProps) {
  const createAccount = useCreateAccount()
  const [accountName, setAccountName] = useState('')
  const [accountType, setAccountType] = useState<AccountType>('Taxable')
  const [submitAttempted, setSubmitAttempted] = useState(false)

  const accountNameError = getAccountNameError(accountName)
  const canSubmit = !accountNameError

  const resetForm = () => {
    setAccountName('')
    setAccountType('Taxable')
    setSubmitAttempted(false)
  }

  const handleOpenChange = (next: boolean) => {
    onOpenChange(next)
    if (!next) resetForm()
  }

  const handleSubmit = () => {
    setSubmitAttempted(true)
    if (!canSubmit) return

    createAccount.mutate(
      { name: normalizeAccountName(accountName), accountType },
      {
        onSuccess: () => {
          handleOpenChange(false)
          toast.success('Account created successfully!')
        },
        onError: (error) => {
          toast.error(`Failed to create account: ${error.message}`)
        },
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add New Account</DialogTitle>
          <DialogDescription>
            Create a new portfolio account to organize your positions.
          </DialogDescription>
        </DialogHeader>
        <form
          onSubmit={(event) => {
            event.preventDefault()
            handleSubmit()
          }}
        >
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="account-name">Account Name</Label>
              <Input
                id="account-name"
                placeholder="e.g., My IRA Account"
                value={accountName}
                onChange={(event) => setAccountName(event.target.value)}
                aria-invalid={submitAttempted && accountNameError ? true : undefined}
              />
              {submitAttempted && accountNameError ? (
                <p className="text-xs text-loss">{accountNameError}</p>
              ) : (
                <p className="text-xs text-text-muted">
                  Use a clear label like "Joint Brokerage" or "Roth IRA".
                </p>
              )}
            </div>
            <div className="grid gap-2">
              <Label htmlFor="account-type">Account Type</Label>
              <Select
                value={accountType}
                onValueChange={(value: string) =>
                  setAccountType(value as AccountType)
                }
              >
                <SelectTrigger id="account-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Taxable">Taxable</SelectItem>
                  <SelectItem value="IRA">IRA</SelectItem>
                  <SelectItem value="Roth">Roth IRA</SelectItem>
                  <SelectItem value="401k">401(k)</SelectItem>
                  <SelectItem value="HSA">HSA</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              type="submit"
              disabled={!canSubmit || createAccount.isPending}
              aria-busy={createAccount.isPending}
            >
              {createAccount.isPending ? 'Creating...' : 'Create Account'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
