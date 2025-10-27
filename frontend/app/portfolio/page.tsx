"use client";

import { useState } from "react";
import { PositionTable } from "@/components/portfolio/PositionTable";
import { PortfolioOverview } from "@/components/portfolio/PortfolioOverview";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAddPosition, useCreateAccount } from "@/lib/hooks/usePortfolio";
import { PlusCircle } from "lucide-react";

export default function PortfolioPage() {
  const addPosition = useAddPosition();
  const createAccount = useCreateAccount();

  // Add Position form state
  const [positionOpen, setPositionOpen] = useState(false);
  const [accountId, setAccountId] = useState("");
  const [symbol, setSymbol] = useState("");
  const [shares, setShares] = useState("");
  const [costBasis, setCostBasis] = useState("");
  const [positionType, setPositionType] = useState<"long" | "short">("long");

  // Add Account form state
  const [accountOpen, setAccountOpen] = useState(false);
  const [accountName, setAccountName] = useState("");
  const [accountType, setAccountType] = useState<
    "IRA" | "Taxable" | "401k" | "Roth" | "HSA"
  >("Taxable");

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
        },
      }
    );
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">
              Portfolio Management
            </h1>
            <p className="mt-2 text-sm text-gray-600">
              Manage your positions, accounts, and view detailed analytics
            </p>
          </div>
          <div className="flex gap-2">
            {/* Add Account Dialog */}
            <Dialog open={accountOpen} onOpenChange={setAccountOpen}>
              <DialogTrigger asChild>
                <Button variant="outline">
                  <PlusCircle className="mr-2 h-4 w-4" />
                  Add Account
                </Button>
              </DialogTrigger>
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
                      onValueChange={(value: any) => setAccountType(value)}
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
              <DialogTrigger asChild>
                <Button>
                  <PlusCircle className="mr-2 h-4 w-4" />
                  Add Position
                </Button>
              </DialogTrigger>
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
                    <Label htmlFor="account-id">Account ID</Label>
                    <Input
                      id="account-id"
                      placeholder="Account ID"
                      value={accountId}
                      onChange={(e) => setAccountId(e.target.value)}
                    />
                    <p className="text-xs text-muted-foreground">
                      Create an account first if you don&apos;t have one
                    </p>
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
                      onValueChange={(value: any) => setPositionType(value)}
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

        {/* Portfolio Analytics */}
        <div className="mb-8">
          <PortfolioOverview />
        </div>

        {/* Positions Table */}
        <Card>
          <CardHeader>
            <CardTitle>Your Positions</CardTitle>
            <CardDescription>
              View and manage all your portfolio positions
            </CardDescription>
          </CardHeader>
          <CardContent>
            <PositionTable />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
