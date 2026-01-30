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
import type { Account } from '@/lib/api/portfolio'

type PositionType = 'long' | 'short'

interface EditPositionDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  accounts: Account[] | undefined
  accountId: string
  symbol: string
  shares: string
  costBasis: string
  positionType: PositionType
  isPending: boolean
  onAccountChange: (value: string) => void
  onSymbolChange: (value: string) => void
  onSharesChange: (value: string) => void
  onCostBasisChange: (value: string) => void
  onPositionTypeChange: (value: PositionType) => void
  onUpdate: () => void
}

export function EditPositionDialog({
  open,
  onOpenChange,
  accounts,
  accountId,
  symbol,
  shares,
  costBasis,
  positionType,
  isPending,
  onAccountChange,
  onSymbolChange,
  onSharesChange,
  onCostBasisChange,
  onPositionTypeChange,
  onUpdate,
}: EditPositionDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Position</DialogTitle>
          <DialogDescription>
            Update the details of your position.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="edit-account-select">Account</Label>
            <Select
              value={accountId}
              onValueChange={onAccountChange}
              disabled={!accounts?.length}
            >
              <SelectTrigger id="edit-account-select">
                <SelectValue placeholder="Select an account" />
              </SelectTrigger>
              <SelectContent>
                {accounts?.map((account) => (
                  <SelectItem key={account.id} value={account.id}>
                    {account.name} ({account.accountType})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="edit-symbol">Symbol</Label>
            <Input
              id="edit-symbol"
              value={symbol}
              onChange={(e) => onSymbolChange(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="edit-shares">Shares</Label>
            <Input
              id="edit-shares"
              type="number"
              value={shares}
              onChange={(e) => onSharesChange(e.target.value)}
              step="0.01"
              min="0"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="edit-cost-basis">Cost Basis (per share)</Label>
            <Input
              id="edit-cost-basis"
              type="number"
              value={costBasis}
              onChange={(e) => onCostBasisChange(e.target.value)}
              step="0.01"
              min="0"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="edit-position-type">Position Type</Label>
            <Select
              value={positionType}
              onValueChange={(value: string) =>
                onPositionTypeChange(value as PositionType)
              }
            >
              <SelectTrigger id="edit-position-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="long">Long</SelectItem>
                <SelectItem value="short">Short</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button onClick={onUpdate} disabled={isPending}>
            {isPending ? 'Updating...' : 'Update Position'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
