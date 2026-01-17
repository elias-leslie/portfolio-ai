'use client'

import { Loader2 } from 'lucide-react'
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
import { Textarea } from '@/components/ui/textarea'
import { useCreatePaperTrade } from '@/lib/hooks/usePaperTrades'

interface NewOrderDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function NewOrderDialog({ open, onOpenChange }: NewOrderDialogProps) {
  const [symbol, setSymbol] = useState('')
  const [action, setAction] = useState<'buy' | 'sell'>('buy')
  const [thesis, setThesis] = useState('')
  const [targetPrice, setTargetPrice] = useState('')
  const [stopLossPct, setStopLossPct] = useState('')

  const createTrade = useCreatePaperTrade()

  const handleSubmit = async () => {
    if (!symbol || !thesis) return

    createTrade.mutate(
      {
        symbol,
        action,
        thesis,
        targetPrice: targetPrice ? Number.parseFloat(targetPrice) : undefined,
        stopLossPct: stopLossPct ? Number.parseFloat(stopLossPct) : undefined,
      },
      {
        onSuccess: () => {
          setSymbol('')
          setAction('buy')
          setThesis('')
          setTargetPrice('')
          setStopLossPct('')
          onOpenChange(false)
        },
      },
    )
  }

  const isFormValid = symbol.length > 0 && thesis.length > 0

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>New Paper Trade</DialogTitle>
          <DialogDescription>
            Create a manual paper trade. Position size will be automatically
            calculated as 5% of available cash.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-2">
              <Label htmlFor="symbol">Symbol</Label>
              <Input
                id="symbol"
                placeholder="AAPL"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                className="font-mono uppercase"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="action">Action</Label>
              <Select
                value={action}
                onValueChange={(val) => setAction(val as 'buy' | 'sell')}
              >
                <SelectTrigger id="action">
                  <SelectValue placeholder="Select action" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="buy">Buy (Long)</SelectItem>
                  <SelectItem value="sell">Sell (Short)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="thesis">Investment Thesis</Label>
            <Textarea
              id="thesis"
              placeholder="Why are you making this trade?"
              value={thesis}
              onChange={(e) => setThesis(e.target.value)}
              rows={3}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-2">
              <Label htmlFor="target">Target Price ($) (Optional)</Label>
              <Input
                id="target"
                type="number"
                placeholder="150.00"
                value={targetPrice}
                onChange={(e) => setTargetPrice(e.target.value)}
                min="0"
                step="0.01"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="stopLoss">Stop Loss (%) (Optional)</Label>
              <Input
                id="stopLoss"
                type="number"
                placeholder="5.0"
                value={stopLossPct}
                onChange={(e) => setStopLossPct(e.target.value)}
                min="0"
                max="100"
                step="0.1"
              />
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={createTrade.isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!isFormValid || createTrade.isPending}
          >
            {createTrade.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Executing...
              </>
            ) : (
              'Place Order'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
