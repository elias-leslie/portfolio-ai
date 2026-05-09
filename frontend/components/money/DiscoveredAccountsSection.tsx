import { PlusCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type {
  HouseholdDiscoveredAccount,
  HouseholdTrackedAccountInput,
} from '@/lib/api/household'

type MoneyAccountsFocus = 'coverage' | 'discovered' | null

type Props = {
  accounts: HouseholdDiscoveredAccount[]
  focus: MoneyAccountsFocus
  onSeed: (seed: HouseholdTrackedAccountInput) => void
}

export function DiscoveredAccountsSection({ accounts, focus, onSeed }: Props) {
  if (accounts.length === 0) return null
  return (
    <div
      className={`rounded-3xl border bg-surface-muted/15 p-5 ${
        focus === 'discovered'
          ? 'border-primary/50 ring-1 ring-primary/30'
          : 'border-border/40'
      }`}
    >
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm font-semibold text-text">
            Possible accounts Jenny found
          </p>
          <p className="mt-1 text-sm text-text-muted">
            Soft-added from statements and transfers. Confirm only real accounts
            you want included in money tracking.
          </p>
        </div>
        <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
          {accounts.length} possible account
          {accounts.length === 1 ? '' : 's'}
        </p>
      </div>

      <div className="mt-4 grid gap-3 xl:grid-cols-2">
        {accounts.map((account) => (
          <div
            key={account.key}
            className="rounded-2xl border border-border/40 bg-surface/70 p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-text">
                  {account.suggestedLabel}
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  {[
                    account.assetGroup,
                    account.accountType,
                    account.institution,
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                </p>
              </div>
              <span className="rounded-full border border-border/40 bg-surface px-2.5 py-1 text-xs text-text-muted">
                {Math.round(account.confidence * 100)}% match
              </span>
            </div>
            <p className="mt-3 text-sm text-text-muted">{account.detail}</p>
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-text-muted">
              <span className="rounded-full border border-border/40 bg-surface px-2.5 py-1">
                Seen {account.occurrenceCount} time
                {account.occurrenceCount === 1 ? '' : 's'}
              </span>
              {account.partialAccount ? (
                <span className="rounded-full border border-border/40 bg-surface px-2.5 py-1">
                  …{account.partialAccount}
                </span>
              ) : null}
            </div>
            <div className="mt-4">
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() =>
                  onSeed({
                    label: account.suggestedLabel,
                    assetGroup: account.assetGroup,
                    accountType: account.accountType,
                    sourceType: account.sourceType,
                    institutionName: account.institution,
                    accountMask: account.partialAccount ?? '',
                    notes: account.sampleDescription ?? '',
                  })
                }
              >
                <PlusCircle className="mr-2 h-4 w-4" />
                Create tracked row
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
