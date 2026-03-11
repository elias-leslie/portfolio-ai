'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { AccountsWithPositionsContent } from '@/components/portfolio/AccountsWithPositions'
import { PositionFormFields } from '@/components/portfolio/PositionFormFields'
import { PortfolioOverview } from '@/components/portfolio/PortfolioOverview'
import {
  type AccountType,
  getAccountNameError,
  getPositionFormErrors,
  isPositionFormValid,
  normalizeAccountName,
  normalizeSymbol,
  type PositionType,
} from '@/components/portfolio/portfolio-form-utils'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
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
import {
  useAccounts,
  useAddPosition,
  useCreateAccount,
} from '@/lib/hooks/usePortfolio'

export default function PortfolioPage() {
  const addPosition = useAddPosition()
  const createAccount = useCreateAccount()
  const {
    data: accounts,
    isLoading: accountsLoading,
    error: accountsError,
    refetch: refetchAccounts,
  } = useAccounts()

  // Add Position form state
  const [positionOpen, setPositionOpen] = useState(false)
  const [accountId, setAccountId] = useState('')
  const [symbol, setSymbol] = useState('')
  const [shares, setShares] = useState('')
  const [costBasis, setCostBasis] = useState('')
  const [positionType, setPositionType] = useState<PositionType>('long')
  const [positionSubmitAttempted, setPositionSubmitAttempted] = useState(false)

  // Add Account form state
  const [accountOpen, setAccountOpen] = useState(false)
  const [accountName, setAccountName] = useState('')
  const [accountType, setAccountType] = useState<AccountType>('Taxable')
  const [accountSubmitAttempted, setAccountSubmitAttempted] = useState(false)
  const positionFormErrors = getPositionFormErrors({
    accountId,
    symbol,
    shares,
    costBasis,
  })
  const canSubmitPositionForm = isPositionFormValid(positionFormErrors)
  const accountNameError = getAccountNameError(accountName)
  const canSubmitAccountForm = !accountNameError

  const resetPositionForm = (nextAccountId: string = '') => {
    setAccountId(nextAccountId)
    setSymbol('')
    setShares('')
    setCostBasis('')
    setPositionType('long')
    setPositionSubmitAttempted(false)
  }

  const openPositionDialog = (nextAccountId?: string) => {
    const defaultAccountId =
      nextAccountId ??
      (accounts?.length === 1 ? accounts[0].id : '')
    resetPositionForm(defaultAccountId)
    setPositionOpen(true)
  }

  const handlePositionDialogChange = (open: boolean) => {
    setPositionOpen(open)
    if (!open) {
      resetPositionForm(accounts?.length === 1 ? accounts[0].id : '')
    }
  }

  const resetAccountForm = () => {
    setAccountName('')
    setAccountType('Taxable')
    setAccountSubmitAttempted(false)
  }

  const handleAccountDialogChange = (open: boolean) => {
    setAccountOpen(open)
    if (!open) {
      resetAccountForm()
    }
  }

  const handleAddPosition = () => {
    setPositionSubmitAttempted(true)
    if (!canSubmitPositionForm) return

    addPosition.mutate(
      {
        accountId,
        symbol: normalizeSymbol(symbol),
        shares: parseFloat(shares),
        costBasis: parseFloat(costBasis),
        positionType,
      },
      {
        onSuccess: () => {
          handlePositionDialogChange(false)
        },
      },
    )
  }

  const handleAddAccount = () => {
    setAccountSubmitAttempted(true)
    if (!canSubmitAccountForm) return

    createAccount.mutate(
      {
        name: normalizeAccountName(accountName),
        accountType,
      },
      {
        onSuccess: () => {
          handleAccountDialogChange(false)
          toast.success('Account created successfully!')
        },
        onError: (error) => {
          toast.error(`Failed to create account: ${error.message}`)
        },
      },
    )
  }

  return (
    <PageContainer className="space-y-10 py-10">
      <PageHeader
        title="Portfolio Coach"
        description="Review your holdings, spot concentration risk, and keep position sizes honest."
      />

      <PortfolioOverview />

      <AccountsWithPositionsContent
        accounts={accounts}
        accountsLoading={accountsLoading}
        accountsError={accountsError}
        onRetryAccounts={() => {
          void refetchAccounts()
        }}
        onAddAccount={() => setAccountOpen(true)}
        onAddPosition={openPositionDialog}
      />

      <Dialog open={accountOpen} onOpenChange={handleAccountDialogChange}>
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
              handleAddAccount()
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
                  aria-invalid={accountSubmitAttempted && accountNameError ? true : undefined}
                />
                {accountSubmitAttempted && accountNameError ? (
                  <p className="text-xs text-loss">{accountNameError}</p>
                ) : (
                  <p className="text-xs text-text-muted">
                    Use a clear label like “Joint Brokerage” or “Roth IRA”.
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
                disabled={!canSubmitAccountForm || createAccount.isPending}
              >
                {createAccount.isPending ? 'Creating...' : 'Create Account'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={positionOpen} onOpenChange={handlePositionDialogChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Position</DialogTitle>
            <DialogDescription>
              Add a new position to your portfolio. Enter the live holding details below.
            </DialogDescription>
          </DialogHeader>
          <form
            onSubmit={(event) => {
              event.preventDefault()
              handleAddPosition()
            }}
          >
            <PositionFormFields
              idPrefix="add-position"
              accounts={accounts}
              accountsLoading={accountsLoading}
              accountId={accountId}
              symbol={symbol}
              shares={shares}
              costBasis={costBasis}
              positionType={positionType}
              errors={positionSubmitAttempted ? positionFormErrors : undefined}
              accountHint={
                !accounts?.length && !accountsLoading ? (
                  <p className="text-xs text-text-muted">
                    Create an account first using the &quot;Add Account&quot; button.
                  </p>
                ) : undefined
              }
              onAccountChange={setAccountId}
              onSymbolChange={setSymbol}
              onSharesChange={setShares}
              onCostBasisChange={setCostBasis}
              onPositionTypeChange={setPositionType}
            />
            <DialogFooter>
              <Button
                type="submit"
                disabled={!canSubmitPositionForm || addPosition.isPending}
              >
                {addPosition.isPending ? 'Adding...' : 'Add Position'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </PageContainer>
  )
}
