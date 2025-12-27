/* eslint react-hooks/incompatible-library: "off" */
'use client';

/* @reactCompiler disable */

import { useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  ColumnDef,
  SortingState,
} from "@tanstack/react-table";
import { usePortfolio, useDeletePosition, useUpdatePosition, useAccounts } from "@/lib/hooks/usePortfolio";
import { PositionWithValue } from "@/lib/api/portfolio";
import { toast } from "sonner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
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
import { Pencil } from "lucide-react";
import Link from "next/link";
import { ConfirmActionDialog } from "@/components/shared/ConfirmActionDialog";

type PositionType = "long" | "short";

export function PositionTable() {
  const { data: portfolio, isLoading } = usePortfolio();
  const { data: accounts } = useAccounts();
  const deletePosition = useDeletePosition();
  const updatePosition = useUpdatePosition();
  const [sorting, setSorting] = useState<SortingState>([]);
  const [positionToDelete, setPositionToDelete] = useState<{ id: string; symbol: string } | null>(null);

  // Edit dialog state
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

  const handleEdit = (position: PositionWithValue) => {
    setEditingPosition(position);
    setEditAccountId(position.accountId);
    setEditSymbol(position.symbol);
    setEditShares(position.shares.toString());
    setEditCostBasis(position.costBasis.toString());
    setEditPositionType(position.positionType as PositionType);
    setEditOpen(true);
  };

  const handleUpdatePosition = () => {
    if (!editingPosition) return;

    updatePosition.mutate(
      {
        positionId: editingPosition.id,
        data: {
          accountId: editAccountId,
          symbol: editSymbol.toUpperCase().trim(),
          shares: parseFloat(editShares),
          costBasis: parseFloat(editCostBasis),
          positionType: editPositionType,
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

  const confirmDeletePosition = async () => {
    if (!positionToDelete) return;
    try {
      await deletePosition.mutateAsync(positionToDelete.id);
      toast.success(`${positionToDelete.symbol} position deleted.`);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to delete position";
      toast.error(`Failed to delete ${positionToDelete.symbol}: ${message}`);
      throw error;
    }
  };

  const isEditFormValid = () => {
    return (
      editAccountId.trim() !== "" &&
      editSymbol.trim() !== "" &&
      parseFloat(editShares) > 0 &&
      parseFloat(editCostBasis) > 0
    );
  };

  const columns: ColumnDef<PositionWithValue>[] = [
    {
      accessorKey: "symbol",
      header: "Symbol",
      cell: ({ row }) => (
        <Link
          href={`/watchlist?symbol=${row.getValue("symbol")}`}
          className="font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 hover:underline transition-colors"
        >
          {row.getValue("symbol")}
        </Link>
      ),
    },
    {
      accessorKey: "position_type",
      header: "Type",
      cell: ({ row }) => {
        const type = row.getValue("position_type") as string;
        return (
          <span
            className={`rounded px-2 py-1 text-xs font-medium ${
              type === "long"
                ? "bg-gain/15 text-gain-strong"
                : "bg-loss/15 text-loss-strong"
            }`}
          >
            {type.toUpperCase()}
          </span>
        );
      },
    },
    {
      accessorKey: "shares",
      header: "Shares",
      cell: ({ row }) => row.getValue("shares"),
    },
    {
      accessorKey: "cost_basis",
      header: "Cost Basis",
      cell: ({ row }) => formatCurrency(row.getValue("cost_basis")),
    },
    {
      accessorKey: "current_price",
      header: "Current Price",
      cell: ({ row }) => formatCurrency(row.getValue("current_price")),
    },
    {
      accessorKey: "current_value",
      header: "Current Value",
      cell: ({ row }) => formatCurrency(row.getValue("current_value")),
    },
    {
      accessorKey: "gain",
      header: "Gain/Loss",
      cell: ({ row }) => {
        const gain = row.getValue("gain") as number;
        return (
          <span className={gain >= 0 ? "text-gain" : "text-loss"}>
            {formatCurrency(gain)}
          </span>
        );
      },
    },
    {
      accessorKey: "gain_pct",
      header: "Gain %",
      cell: ({ row }) => {
        const gainPct = row.getValue("gain_pct") as number;
        return (
          <span className={gainPct >= 0 ? "text-gain" : "text-loss"}>
            {formatPercent(gainPct)}
          </span>
        );
      },
    },
    {
      id: "actions",
      header: "Actions",
      cell: ({ row }) => (
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleEdit(row.original)}
          >
            <Pencil className="h-3 w-3 mr-1" />
            Edit
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setPositionToDelete({
                id: row.original.id,
                symbol: row.original.symbol,
              });
            }}
            disabled={deletePosition.isPending}
          >
            Delete
          </Button>
        </div>
      ),
    },
  ];

  const table = useReactTable({
    data: portfolio?.positions || [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    onSortingChange: setSorting,
    state: {
      sorting,
    },
  });

  const deleteDialog = (
    <ConfirmActionDialog
      open={!!positionToDelete}
      onOpenChange={(open) => {
        if (!open) {
          setPositionToDelete(null);
        }
      }}
      title={
        positionToDelete
          ? `Delete ${positionToDelete.symbol}`
          : "Delete position"
      }
      description="This action permanently removes the position from your portfolio."
      confirmLabel="Delete position"
      isPending={deletePosition.isPending}
      onConfirm={confirmDeletePosition}
    />
  );

  if (isLoading) {
    return (
      <>
        <div className="rounded-md border border-border bg-surface/50">
          <div className="flex h-64 items-center justify-center">
            <div className="animate-pulse text-text-muted">
              Loading positions...
            </div>
          </div>
        </div>
        {deleteDialog}
      </>
    );
  }

  if (!portfolio?.positions.length) {
    return (
      <>
        <div className="rounded-md border border-border bg-surface/50">
          <div className="flex h-64 items-center justify-center text-text-muted">
            No positions yet. Add your first position to get started.
          </div>
        </div>
        {deleteDialog}
      </>
    );
  }

  return (
    <>
      <div className="rounded-md border border-border bg-surface/40">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.map((row) => {
              const gain = row.original.gain ?? 0;
              const bgClass = gain >= 0
                ? "bg-gain/10 hover:bg-gain/20"
                : "bg-loss/10 hover:bg-loss/20";

              return (
                <TableRow key={row.id} className={bgClass}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

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
              >
                <SelectTrigger id="edit-account-select">
                  <SelectValue placeholder="Select an account" />
                </SelectTrigger>
                <SelectContent>
                  {accounts?.map((account) => (
                    <SelectItem key={account.id} value={account.id}>
                      {account.name} ({account.accountType})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-symbol">Symbol</Label>
              <Input
                id="edit-symbol"
                placeholder="e.g., AAPL"
                value={editSymbol}
                onChange={(e) => setEditSymbol(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-shares">Shares</Label>
              <Input
                id="edit-shares"
                type="number"
                placeholder="e.g., 100"
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
                placeholder="e.g., 150.00"
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
              disabled={!isEditFormValid() || updatePosition.isPending}
            >
              {updatePosition.isPending ? "Updating..." : "Update Position"}
            </Button>
          </DialogFooter>
      </DialogContent>
    </Dialog>
      {deleteDialog}
    </>
  );
}
