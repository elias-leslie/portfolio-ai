"use client";

import { useState } from "react";
import { useAccounts, usePortfolio, useDeleteAccount, useDeletePosition, useUpdatePosition } from "@/lib/hooks/usePortfolio";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
import { toast } from "sonner";
import { Trash2, Pencil, PlusCircle } from "lucide-react";
import type { PositionWithValue } from "@/lib/api/portfolio";

type PositionType = "long" | "short";

interface AccountsWithPositionsProps {
  onAddAccount?: () => void;
  onAddPosition?: (accountId: string) => void;
}

export function AccountsWithPositions({ onAddAccount, onAddPosition }: AccountsWithPositionsProps) {
  const { data: accounts, isLoading: accountsLoading } = useAccounts();
  const { data: portfolio, isLoading: portfolioLoading } = usePortfolio();
  const deleteAccount = useDeleteAccount();
  const deletePosition = useDeletePosition();
  const updatePosition = useUpdatePosition();

  // Edit position dialog state
  const [editOpen, setEditOpen] = useState(false);
  const [editingPosition, setEditingPosition] = useState<PositionWithValue | null>(null);
  const [editAccountId, setEditAccountId] = useState("");
  const [editSymbol, setEditSymbol] = useState("");
  const [editShares, setEditShares] = useState("");
  const [editCostBasis, setEditCostBasis] = useState("");
  const [editPositionType, setEditPositionType] = useState<PositionType>("long");

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
    }).format(value);
  };

  const formatPercent = (value: number) => {
    return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
  };

  const handleDeleteAccount = (accountId: string, accountName: string) => {
    const positionsInAccount = portfolio?.positions.filter(
      (p) => p.account_id === accountId
    ) || [];

    const confirmMessage = positionsInAccount.length > 0
      ? `Are you sure you want to delete "${accountName}"? This will also delete ${positionsInAccount.length} position${positionsInAccount.length > 1 ? "s" : ""} in this account.`
      : `Are you sure you want to delete "${accountName}"?`;

    if (confirm(confirmMessage)) {
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

  const handleDeletePosition = (positionId: string, symbol: string) => {
    if (confirm(`Are you sure you want to delete ${symbol}?`)) {
      deletePosition.mutate(positionId, {
        onSuccess: () => {
          toast.success("Position deleted successfully!");
        },
        onError: (error) => {
          toast.error(`Failed to delete position: ${error.message}`);
        },
      });
    }
  };

  const handleEditPosition = (position: PositionWithValue) => {
    setEditingPosition(position);
    setEditAccountId(position.account_id);
    setEditSymbol(position.symbol);
    setEditShares(position.shares.toString());
    setEditCostBasis(position.cost_basis.toString());
    setEditPositionType(position.position_type as PositionType);
    setEditOpen(true);
  };

  const handleUpdatePosition = () => {
    if (!editingPosition) return;

    updatePosition.mutate(
      {
        positionId: editingPosition.id,
        data: {
          account_id: editAccountId,
          symbol: editSymbol.toUpperCase().trim(),
          shares: parseFloat(editShares),
          cost_basis: parseFloat(editCostBasis),
          position_type: editPositionType,
        },
      },
      {
        onSuccess: () => {
          setEditOpen(false);
          setEditingPosition(null);
          toast.success("Position updated successfully!");
        },
        onError: (error) => {
          toast.error(`Failed to update position: ${error.message}`);
        },
      }
    );
  };

  // Group positions by account
  const getAccountPositions = (accountId: string) => {
    return portfolio?.positions.filter((p) => p.account_id === accountId) || [];
  };

  const getAccountTotalValue = (accountId: string) => {
    const positions = getAccountPositions(accountId);
    return positions.reduce((sum, p) => sum + (p.current_value || 0), 0);
  };

  const getAccountTotalGain = (accountId: string) => {
    const positions = getAccountPositions(accountId);
    const totalValue = positions.reduce((sum, p) => sum + (p.current_value || 0), 0);
    const totalCost = positions.reduce((sum, p) => sum + (p.shares * p.cost_basis), 0);
    return totalCost > 0 ? ((totalValue - totalCost) / totalCost) * 100 : 0;
  };

  if (accountsLoading || portfolioLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Accounts & Positions</CardTitle>
          <CardDescription>Loading accounts and positions...</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (!accounts || accounts.length === 0) {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Accounts & Positions</CardTitle>
              <CardDescription>Organize your portfolio by account</CardDescription>
            </div>
            {onAddAccount && (
              <Button variant="outline" size="sm" onClick={onAddAccount}>
                <PlusCircle className="mr-2 h-4 w-4" />
                Add Account
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-text-muted">
            No accounts yet. Click &quot;Add Account&quot; above to start managing your portfolio.
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Accounts & Positions</CardTitle>
              <CardDescription>
                {accounts.length} account{accounts.length !== 1 ? "s" : ""} • {portfolio?.positions.length || 0} position{portfolio?.positions.length !== 1 ? "s" : ""}
              </CardDescription>
            </div>
            {onAddAccount && (
              <Button variant="outline" size="sm" onClick={onAddAccount}>
                <PlusCircle className="mr-2 h-4 w-4" />
                Add Account
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <Accordion type="single" collapsible className="w-full">
            {accounts.map((account) => {
              const positions = getAccountPositions(account.id);
              const totalValue = getAccountTotalValue(account.id);
              const totalGain = getAccountTotalGain(account.id);

              return (
                <AccordionItem key={account.id} value={account.id} className="border rounded-lg mb-3 last:mb-0">
                  <AccordionTrigger className="px-4 hover:no-underline">
                    <div className="flex items-center justify-between w-full pr-4">
                      <div className="flex flex-col items-start gap-1">
                        <div className="flex items-center gap-3">
                          <span className="font-semibold text-base">{account.name}</span>
                          <span className="text-xs text-text-muted bg-surface-muted px-2 py-0.5 rounded">
                            {account.account_type}
                          </span>
                        </div>
                        <div className="flex items-center gap-4 text-sm">
                          <span className="text-text-muted">
                            {positions.length} position{positions.length !== 1 ? "s" : ""}
                          </span>
                          {positions.length > 0 && (
                            <>
                              <span className="text-text">
                                {formatCurrency(totalValue)}
                              </span>
                              <span className={totalGain >= 0 ? "text-profit" : "text-loss"}>
                                {formatPercent(totalGain)}
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteAccount(account.id, account.name);
                        }}
                        disabled={deleteAccount.isPending}
                        className="h-8 w-8 p-0 ml-2"
                      >
                        <Trash2 className="h-4 w-4 text-loss" />
                      </Button>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="px-4 pb-4">
                    {onAddPosition && (
                      <div className="mb-3 flex justify-end">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => onAddPosition(account.id)}
                        >
                          <PlusCircle className="mr-2 h-4 w-4" />
                          Add Position
                        </Button>
                      </div>
                    )}
                    {positions.length === 0 ? (
                      <div className="py-8 text-center text-sm text-text-muted">
                        No positions in this account yet. Click &quot;Add Position&quot; above to get started.
                      </div>
                    ) : (
                      <div className="rounded-md border border-border bg-surface/50 overflow-hidden">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Symbol</TableHead>
                              <TableHead className="text-right">Shares</TableHead>
                              <TableHead className="text-right">Cost Basis</TableHead>
                              <TableHead className="text-right">Current Price</TableHead>
                              <TableHead className="text-right">Value</TableHead>
                              <TableHead className="text-right">Gain/Loss</TableHead>
                              <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {positions.map((position) => {
                              const gainLoss = position.current_value
                                ? ((position.current_value - position.shares * position.cost_basis) /
                                    (position.shares * position.cost_basis)) * 100
                                : 0;

                              return (
                                <TableRow key={position.id}>
                                  <TableCell className="font-medium">{position.symbol}</TableCell>
                                  <TableCell className="text-right">{position.shares}</TableCell>
                                  <TableCell className="text-right">
                                    {formatCurrency(position.cost_basis)}
                                  </TableCell>
                                  <TableCell className="text-right">
                                    {position.current_price
                                      ? formatCurrency(position.current_price)
                                      : "—"}
                                  </TableCell>
                                  <TableCell className="text-right">
                                    {position.current_value
                                      ? formatCurrency(position.current_value)
                                      : "—"}
                                  </TableCell>
                                  <TableCell
                                    className={`text-right ${
                                      gainLoss >= 0 ? "text-profit" : "text-loss"
                                    }`}
                                  >
                                    {position.current_value ? formatPercent(gainLoss) : "—"}
                                  </TableCell>
                                  <TableCell className="text-right">
                                    <div className="flex items-center justify-end gap-1">
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => handleEditPosition(position)}
                                        className="h-8 w-8 p-0"
                                      >
                                        <Pencil className="h-3.5 w-3.5" />
                                      </Button>
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => handleDeletePosition(position.id, position.symbol)}
                                        disabled={deletePosition.isPending}
                                        className="h-8 w-8 p-0"
                                      >
                                        <Trash2 className="h-3.5 w-3.5 text-loss" />
                                      </Button>
                                    </div>
                                  </TableCell>
                                </TableRow>
                              );
                            })}
                          </TableBody>
                        </Table>
                      </div>
                    )}
                  </AccordionContent>
                </AccordionItem>
              );
            })}
          </Accordion>
        </CardContent>
      </Card>

      {/* Edit Position Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Position</DialogTitle>
            <DialogDescription>
              Update the details of your position.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="edit-account-select">Account</Label>
              <Select
                value={editAccountId}
                onValueChange={setEditAccountId}
                disabled={!accounts?.length}
              >
                <SelectTrigger id="edit-account-select">
                  <SelectValue placeholder="Select an account" />
                </SelectTrigger>
                <SelectContent>
                  {accounts?.map((account) => (
                    <SelectItem key={account.id} value={account.id}>
                      {account.name} ({account.account_type})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-symbol">Symbol</Label>
              <Input
                id="edit-symbol"
                value={editSymbol}
                onChange={(e) => setEditSymbol(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-shares">Shares</Label>
              <Input
                id="edit-shares"
                type="number"
                value={editShares}
                onChange={(e) => setEditShares(e.target.value)}
                step="0.01"
                min="0"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-cost-basis">Cost Basis (per share)</Label>
              <Input
                id="edit-cost-basis"
                type="number"
                value={editCostBasis}
                onChange={(e) => setEditCostBasis(e.target.value)}
                step="0.01"
                min="0"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-position-type">Position Type</Label>
              <Select
                value={editPositionType}
                onValueChange={(value: string) =>
                  setEditPositionType(value as PositionType)
                }
              >
                <SelectTrigger id="edit-position-type">
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
              onClick={handleUpdatePosition}
              disabled={updatePosition.isPending}
            >
              {updatePosition.isPending ? "Updating..." : "Update Position"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
