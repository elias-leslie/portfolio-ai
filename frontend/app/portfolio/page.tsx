"use client";

import { useState } from "react";
import { PortfolioOverview } from "@/components/portfolio/PortfolioOverview";
import { AccountsWithPositions } from "@/components/portfolio/AccountsWithPositions";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAddPosition, useCreateAccount, useAccounts } from "@/lib/hooks/usePortfolio";

type PositionType = "long" | "short";
type AccountType = "IRA" | "Taxable" | "401k" | "Roth" | "HSA";

export default function PortfolioPage() {
  const addPosition = useAddPosition();
  const createAccount = useCreateAccount();
  const { data: accounts, isLoading: accountsLoading } = useAccounts();

  // Add Position form state
  const [positionOpen, setPositionOpen] = useState(false);
  const [accountId, setAccountId] = useState("");
  const [symbol, setSymbol] = useState("");
  const [shares, setShares] = useState("");
  const [costBasis, setCostBasis] = useState("");
  const [positionType, setPositionType] = useState<PositionType>("long");

  // Add Account form state
  const [accountOpen, setAccountOpen] = useState(false);
  const [accountName, setAccountName] = useState("");
  const [accountType, setAccountType] = useState<AccountType>("Taxable");

  // Form validation
  const isPositionFormValid = () => {
    return (
      accountId.trim() !== "" &&
      symbol.trim() !== "" &&
      parseFloat(shares) > 0 &&
      parseFloat(costBasis) > 0
    );
  };

  const isAccountFormValid = () => {
    return accountName.trim() !== "";
  };

  // Handle Add Position submit
  const handleAddPosition = () => {
    if (!isPositionFormValid()) return;

    addPosition.mutate(
      {
        account_id: accountId,
        symbol: symbol.toUpperCase().trim(),
        shares: parseFloat(shares),
        cost_basis: parseFloat(costBasis),
        position_type: positionType,
      },
      {
        onSuccess: () => {
          // Reset form
          setAccountId("");
          setSymbol("");
          setShares("");
          setCostBasis("");
          setPositionType("long");
          setPositionOpen(false);
          toast.success("Position added successfully!");
        },
        onError: (error) => {
          toast.error(`Failed to add position: ${error.message}`);
        },
      }
    );
  };

  // Handle Add Account submit
  const handleAddAccount = () => {
    if (!isAccountFormValid()) return;

    createAccount.mutate(
      {
        name: accountName,
        account_type: accountType,
      },
      {
        onSuccess: () => {
          // Reset form
          setAccountName("");
          setAccountType("Taxable");
          setAccountOpen(false);
          toast.success("Account created successfully!");
        },
        onError: (error) => {
          toast.error(`Failed to create account: ${error.message}`);
        },
      }
    );
  };

  return (
    <div className="bg-bg">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-10 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-primary via-accent to-primary bg-clip-text text-transparent">
              Portfolio Management
            </h1>
            <p className="mt-3 text-base text-text-muted">
              Manage your positions, accounts, and view detailed analytics
            </p>
          </div>
          {/* Removed buttons - now in AccountsWithPositions card */}
        </div>

        {/* Portfolio Analytics */}
        <div className="mb-10">
          <PortfolioOverview />
        </div>

        {/* Accounts with Positions */}
        <AccountsWithPositions
          onAddAccount={() => setAccountOpen(true)}
          onAddPosition={(accountId) => {
            setAccountId(accountId);
            setPositionOpen(true);
          }}
        />

        {/* Hidden Dialogs */}
        <div className="hidden">
          {/* Add Account Dialog */}
          <Dialog open={accountOpen} onOpenChange={setAccountOpen}>
            <DialogContent>
                <DialogHeader>
                  <DialogTitle>Add New Account</DialogTitle>
                  <DialogDescription>
                    Create a new portfolio account to organize your positions.
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  <div className="grid gap-2">
                    <Label htmlFor="account-name">Account Name</Label>
                    <Input
                      id="account-name"
                      placeholder="e.g., My IRA Account"
                      value={accountName}
                      onChange={(e) => setAccountName(e.target.value)}
                    />
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
                    onClick={handleAddAccount}
                    disabled={!isAccountFormValid() || createAccount.isPending}
                  >
                    {createAccount.isPending ? "Creating..." : "Create Account"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            {/* Add Position Dialog */}
            <Dialog open={positionOpen} onOpenChange={setPositionOpen}>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Add Position</DialogTitle>
                  <DialogDescription>
                    Add a new position to your portfolio. Enter the details
                    below.
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  <div className="grid gap-2">
                    <Label htmlFor="account-select">Account</Label>
                    <Select
                      value={accountId}
                      onValueChange={setAccountId}
                      disabled={accountsLoading || !accounts?.length}
                    >
                      <SelectTrigger id="account-select">
                        <SelectValue placeholder={
                          accountsLoading
                            ? "Loading accounts..."
                            : !accounts?.length
                            ? "No accounts available"
                            : "Select an account"
                        } />
                      </SelectTrigger>
                      <SelectContent>
                        {accounts?.map((account) => (
                          <SelectItem key={account.id} value={account.id}>
                            {account.name} ({account.account_type})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {!accounts?.length && !accountsLoading && (
                      <p className="text-xs text-text-muted">
                        Create an account first using the &quot;Add Account&quot; button
                      </p>
                    )}
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="symbol">Symbol</Label>
                    <Input
                      id="symbol"
                      placeholder="e.g., AAPL"
                      value={symbol}
                      onChange={(e) => setSymbol(e.target.value)}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="shares">Shares</Label>
                    <Input
                      id="shares"
                      type="number"
                      placeholder="e.g., 100"
                      value={shares}
                      onChange={(e) => setShares(e.target.value)}
                      step="0.01"
                      min="0"
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="cost-basis">Cost Basis (per share)</Label>
                    <Input
                      id="cost-basis"
                      type="number"
                      placeholder="e.g., 150.00"
                      value={costBasis}
                      onChange={(e) => setCostBasis(e.target.value)}
                      step="0.01"
                      min="0"
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="position-type">Position Type</Label>
                    <Select
                      value={positionType}
                      onValueChange={(value: string) =>
                        setPositionType(value as PositionType)
                      }
                    >
                      <SelectTrigger id="position-type">
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
                  <Button
                    onClick={handleAddPosition}
                    disabled={!isPositionFormValid() || addPosition.isPending}
                  >
                    {addPosition.isPending ? "Adding..." : "Add Position"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
        </div>
      </div>
    </div>
  );
}
