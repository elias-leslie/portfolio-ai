'use client'

import { useEffect, useState } from 'react'
import { useSetHouseholdTransactionOwner } from '@/lib/hooks/useHousehold'
import {
  type InlineComboboxCommitOptions,
  InlineComboboxField,
} from './InlineComboboxField'
import { buildOwnerOptions } from './owner-options'

interface TransactionOwnerSelectProps {
  transactionId: string
  fieldId?: string
  itemLabel: string
  ownerName?: string | null
  ownerSource?: string | null
  className?: string
}

export function TransactionOwnerSelect({
  transactionId,
  fieldId,
  itemLabel,
  ownerName,
  ownerSource,
  className,
}: TransactionOwnerSelectProps) {
  const owner = ownerName?.trim() ?? ''
  const [applyToMerchant, setApplyToMerchant] = useState(
    ownerSource === 'merchant_rule',
  )
  const setOwner = useSetHouseholdTransactionOwner()
  const sourceLabel = owner
    ? ownerSource?.replace(/_/g, ' ') || 'transaction owner'
    : 'unassigned'

  useEffect(() => {
    setApplyToMerchant(ownerSource === 'merchant_rule')
  }, [ownerSource])

  function commit(nextOwner: string, options?: InlineComboboxCommitOptions) {
    void setOwner.mutateAsync({
      transactionId,
      ownerName: nextOwner.trim() || null,
      applyToMerchant: options?.applyRule === true,
    })
  }

  return (
    <div className={className}>
      <InlineComboboxField
        id={`transaction-owner-${fieldId ?? transactionId}`}
        label={`Owner for ${itemLabel}`}
        value={owner}
        options={buildOwnerOptions([owner])}
        placeholder="Owner"
        disabled={setOwner.isPending}
        ruleLabel="Merchant owner rule"
        ruleChecked={applyToMerchant}
        onRuleCheckedChange={setApplyToMerchant}
        className="w-[190px]"
        onCommit={commit}
      />
      <p className="mt-1 text-[10px] capitalize leading-none text-text-muted">
        {sourceLabel}
      </p>
    </div>
  )
}
