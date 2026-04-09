import type { ReactNode } from 'react'
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
import type { PositionFormErrors, PositionType } from './portfolio-form-utils'

interface PositionFormFieldsProps {
  idPrefix: string
  accounts: Account[] | undefined
  accountsLoading?: boolean
  accountId: string
  symbol: string
  shares: string
  costBasis: string
  positionType: PositionType
  errors?: PositionFormErrors
  accountHint?: ReactNode
  symbolPlaceholder?: string
  onAccountChange: (value: string) => void
  onSymbolChange: (value: string) => void
  onSharesChange: (value: string) => void
  onCostBasisChange: (value: string) => void
  onPositionTypeChange: (value: PositionType) => void
}

export function PositionFormFields({
  idPrefix,
  accounts,
  accountsLoading = false,
  accountId,
  symbol,
  shares,
  costBasis,
  positionType,
  errors,
  accountHint,
  symbolPlaceholder = 'e.g., AAPL',
  onAccountChange,
  onSymbolChange,
  onSharesChange,
  onCostBasisChange,
  onPositionTypeChange,
}: PositionFormFieldsProps) {
  const accountPlaceholder = accountsLoading
    ? 'Loading accounts...'
    : !accounts?.length
      ? 'No accounts available'
      : 'Select an account'

  return (
    <div className="grid gap-4 py-4">
      <div className="grid gap-2">
        <Label htmlFor={`${idPrefix}-account-select`}>Account</Label>
        <Select
          value={accountId}
          onValueChange={onAccountChange}
          disabled={accountsLoading || !accounts?.length}
        >
          <SelectTrigger
            id={`${idPrefix}-account-select`}
            aria-invalid={errors?.accountId ? true : undefined}
          >
            <SelectValue placeholder={accountPlaceholder} />
          </SelectTrigger>
          <SelectContent>
            {accounts?.map((account) => (
              <SelectItem key={account.id} value={account.id}>
                {account.name} ({account.accountType})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {errors?.accountId ? (
          <p className="text-xs text-loss">{errors.accountId}</p>
        ) : (
          accountHint
        )}
      </div>

      <div className="grid gap-2">
        <Label htmlFor={`${idPrefix}-symbol`}>Symbol</Label>
        <Input
          id={`${idPrefix}-symbol`}
          placeholder={symbolPlaceholder}
          value={symbol}
          onChange={(event) => onSymbolChange(event.target.value)}
          autoCapitalize="characters"
          autoCorrect="off"
          spellCheck={false}
          aria-invalid={errors?.symbol ? true : undefined}
        />
        {errors?.symbol ? (
          <p className="text-xs text-loss">{errors.symbol}</p>
        ) : null}
      </div>

      <div className="grid gap-2">
        <Label htmlFor={`${idPrefix}-shares`}>Shares</Label>
        <Input
          id={`${idPrefix}-shares`}
          type="number"
          placeholder="e.g., 100"
          value={shares}
          onChange={(event) => onSharesChange(event.target.value)}
          step="0.01"
          min="0"
          inputMode="decimal"
          aria-invalid={errors?.shares ? true : undefined}
        />
        {errors?.shares ? (
          <p className="text-xs text-loss">{errors.shares}</p>
        ) : null}
      </div>

      <div className="grid gap-2">
        <Label htmlFor={`${idPrefix}-cost-basis`}>Cost Basis (per share)</Label>
        <Input
          id={`${idPrefix}-cost-basis`}
          type="number"
          placeholder="e.g., 150.00"
          value={costBasis}
          onChange={(event) => onCostBasisChange(event.target.value)}
          step="0.01"
          min="0"
          inputMode="decimal"
          aria-invalid={errors?.costBasis ? true : undefined}
        />
        {errors?.costBasis ? (
          <p className="text-xs text-loss">{errors.costBasis}</p>
        ) : null}
      </div>

      <div className="grid gap-2">
        <Label htmlFor={`${idPrefix}-position-type`}>Position Type</Label>
        <Select
          value={positionType}
          onValueChange={(value: string) =>
            onPositionTypeChange(value as PositionType)
          }
        >
          <SelectTrigger id={`${idPrefix}-position-type`}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="long">Long</SelectItem>
            <SelectItem value="short">Short</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}
