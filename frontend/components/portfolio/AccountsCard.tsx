'use client'

import { Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { ConfirmActionDialog } from '@/components/shared/ConfirmActionDialog'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { useAccounts, useDeleteAccount } from '@/lib/hooks/usePortfolio'

function AccountsSkeleton() {
  return (
    <Card data-testid="accounts-skeleton">
      <CardHeader>
        <div className="space-y-2">
          <div className="h-5 w-32 animate-pulse rounded-md bg-surface-muted/60" />
          <div className="h-3 w-52 animate-pulse rounded-md bg-surface-muted/40" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {[0, 1, 2].map((item) => (
            <div
              key={`account-skeleton-${item}`}
              className="flex items-center justify-between rounded-xl border border-border/50 bg-surface/40 p-3"
            >
              <div className="space-y-2">
                <div className="h-4 w-36 animate-pulse rounded bg-surface-muted/80" />
                <div className="h-3 w-24 animate-pulse rounded bg-surface-muted/60" />
              </div>
              <div className="h-8 w-8 rounded-full bg-surface-muted/60" />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

export function AccountsCard() {
  const { data: accounts, isLoading } = useAccounts()
  const deleteAccount = useDeleteAccount()
  const [accountToDelete, setAccountToDelete] = useState<{
    id: string
    name: string
  } | null>(null)

  const confirmDeleteAccount = async () => {
    if (!accountToDelete) return
    try {
      await deleteAccount.mutateAsync(accountToDelete.id)
      toast.success(`Account "${accountToDelete.name}" deleted successfully!`)
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to delete account'
      toast.error(`Failed to delete account: ${errorMessage}`)
      throw error
    }
  }

  if (isLoading) {
    return <AccountsSkeleton />
  }

  if (!accounts || accounts.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Accounts</CardTitle>
          <CardDescription>Manage your portfolio accounts</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-text-muted">
            No accounts yet. Create one to start managing your portfolio.
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Accounts</CardTitle>
        <CardDescription>
          {accounts.length} account{accounts.length !== 1 ? 's' : ''}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {accounts.map((account) => (
            <div
              key={account.id}
              className="flex items-center justify-between rounded-lg border border-border bg-surface/40 p-3"
            >
              <div>
                <div className="font-medium text-sm">{account.name}</div>
                <div className="text-xs text-text-muted mt-1">
                  {account.accountType}
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  setAccountToDelete({
                    id: account.id,
                    name: account.name,
                  })
                }
                disabled={deleteAccount.isPending}
                className="h-8 w-8 p-0"
              >
                <Trash2 className="h-4 w-4 text-loss" />
              </Button>
            </div>
          ))}
        </div>
      </CardContent>
      <ConfirmActionDialog
        open={!!accountToDelete}
        onOpenChange={(open) => {
          if (!open) {
            setAccountToDelete(null)
          }
        }}
        title="Delete account"
        description={
          accountToDelete
            ? `Deleting "${accountToDelete.name}" will also remove every position assigned to it. This action cannot be undone.`
            : undefined
        }
        confirmLabel="Delete account"
        isPending={deleteAccount.isPending}
        onConfirm={confirmDeleteAccount}
      />
    </Card>
  )
}
