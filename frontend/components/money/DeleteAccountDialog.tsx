import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { HouseholdAccountSummary } from '@/lib/api/household'

type Props = {
  account: HouseholdAccountSummary | null
  isPending: boolean
  onCancel: () => void
  onConfirm: (account: HouseholdAccountSummary) => void
}

export function DeleteAccountDialog({
  account,
  isPending,
  onCancel,
  onConfirm,
}: Props) {
  return (
    <Dialog
      open={Boolean(account)}
      onOpenChange={(open) => {
        if (!open && !isPending) onCancel()
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Archive account</DialogTitle>
          <DialogDescription>
            Remove{' '}
            <span className="font-medium text-text">
              {account?.label ?? 'this account'}
            </span>{' '}
            from active Money accounts and totals. Existing supporting documents
            will stay in evidence history.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={onCancel}
            disabled={isPending}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={() => {
              if (account) onConfirm(account)
            }}
            disabled={!account || isPending}
            aria-busy={isPending}
          >
            {isPending ? 'Archiving...' : 'Archive account'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
