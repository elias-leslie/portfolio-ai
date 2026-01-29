import { Briefcase } from 'lucide-react'
import { useState } from 'react'
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
import type { TradeRecommendation } from '@/lib/api/recommendations'
import { useAccounts } from '@/lib/hooks/usePortfolio'

interface TrackInPortfolioModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  recommendation: TradeRecommendation | null
  onConfirm: (accountId: string, shares: number) => void
  isLoading: boolean
}

export function TrackInPortfolioModal({
  open,
  onOpenChange,
  recommendation,
  onConfirm,
  isLoading,
}: TrackInPortfolioModalProps) {
  const { data: accounts } = useAccounts()
  const [selectedAccount, setSelectedAccount] = useState<string>('')
  const [shares, setShares] = useState<number>(0)

  // Filter out paper accounts
  const realAccounts = accounts?.filter((a) => a.accountType !== 'paper') || []

  // Reset form when modal opens with new recommendation
  const handleOpenChange = (newOpen: boolean) => {
    if (newOpen && recommendation) {
      setShares(recommendation.positionSizeShares)
      setSelectedAccount('')
    }
    onOpenChange(newOpen)
  }

  const handleConfirm = () => {
    if (selectedAccount && shares > 0) {
      onConfirm(selectedAccount, shares)
    }
  }

  if (!recommendation) return null

  const totalCost = shares * recommendation.currentPrice

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Briefcase className="h-5 w-5" />
            Track {recommendation.symbol} in Portfolio
          </DialogTitle>
          <DialogDescription>
            Add this position to your real portfolio. This is for tracking
            purposes only - you must execute the actual trade with your broker.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {/* Account Selection */}
          <div className="grid gap-2">
            <Label htmlFor="account">Select Account</Label>
            {realAccounts.length === 0 ? (
              <p className="text-sm text-text-muted">
                No real accounts found. Create an account on the Portfolio page
                first.
              </p>
            ) : (
              <Select
                value={selectedAccount}
                onValueChange={setSelectedAccount}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Choose an account..." />
                </SelectTrigger>
                <SelectContent>
                  {realAccounts.map((account) => (
                    <SelectItem key={account.id} value={account.id}>
                      {account.name} ({account.accountType})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          {/* Shares Input */}
          <div className="grid gap-2">
            <Label htmlFor="shares">Number of Shares</Label>
            <Input
              id="shares"
              type="number"
              min={1}
              value={shares}
              onChange={(e) => setShares(parseInt(e.target.value, 10) || 0)}
            />
            <p className="text-xs text-text-muted">
              Suggested: {recommendation.positionSizeShares} shares ($
              {recommendation.positionSizeDollars.toLocaleString()})
            </p>
          </div>

          {/* Summary */}
          <div className="rounded-lg border border-border bg-surface-muted/50 p-3">
            <div className="flex justify-between text-sm">
              <span>Current Price:</span>
              <span className="font-medium">
                ${recommendation.currentPrice.toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span>Shares:</span>
              <span className="font-medium">{shares}</span>
            </div>
            <div className="mt-2 flex justify-between border-t border-border pt-2 text-sm font-medium">
              <span>Total Cost:</span>
              <span>
                $
                {totalCost.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                })}
              </span>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={
              !selectedAccount ||
              shares <= 0 ||
              isLoading ||
              realAccounts.length === 0
            }
          >
            {isLoading ? 'Adding...' : 'Add to Portfolio'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
