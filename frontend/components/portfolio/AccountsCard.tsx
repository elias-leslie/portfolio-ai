"use client";

import { useAccounts, useDeleteAccount } from "@/lib/hooks/usePortfolio";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";

export function AccountsCard() {
  const { data: accounts, isLoading } = useAccounts();
  const deleteAccount = useDeleteAccount();

  const handleDelete = (accountId: string, accountName: string) => {
    if (
      confirm(
        `Are you sure you want to delete "${accountName}"? This will also delete all positions in this account.`
      )
    ) {
      deleteAccount.mutate(accountId, {
        onSuccess: () => {
          toast.success("Account deleted successfully!");
        },
        onError: (error) => {
          toast.error(`Failed to delete account: ${error.message}`);
        },
      });
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Accounts</CardTitle>
          <CardDescription>Loading accounts...</CardDescription>
        </CardHeader>
      </Card>
    );
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
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Accounts</CardTitle>
        <CardDescription>
          {accounts.length} account{accounts.length !== 1 ? "s" : ""}
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
                  {account.account_type}
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleDelete(account.id, account.name)}
                disabled={deleteAccount.isPending}
                className="h-8 w-8 p-0"
              >
                <Trash2 className="h-4 w-4 text-loss" />
              </Button>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
