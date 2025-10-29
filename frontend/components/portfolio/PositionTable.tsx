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
import { usePortfolio, useDeletePosition } from "@/lib/hooks/usePortfolio";
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

export function PositionTable() {
  const { data: portfolio, isLoading } = usePortfolio();
  const deletePosition = useDeletePosition();
  const [sorting, setSorting] = useState<SortingState>([]);

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

  const columns: ColumnDef<PositionWithValue>[] = [
    {
      accessorKey: "symbol",
      header: "Symbol",
      cell: ({ row }) => (
        <span className="font-medium">{row.getValue("symbol")}</span>
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
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            if (confirm("Are you sure you want to delete this position?")) {
              deletePosition.mutate(row.original.id, {
                onSuccess: () => {
                  toast.success("Position deleted successfully!");
                },
                onError: (error) => {
                  toast.error(`Failed to delete position: ${error.message}`);
                },
              });
            }
          }}
          disabled={deletePosition.isPending}
        >
          Delete
        </Button>
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

  if (isLoading) {
    return (
      <div className="rounded-md border border-border bg-surface/50">
        <div className="flex h-64 items-center justify-center">
          <div className="animate-pulse text-text-muted">
            Loading positions...
          </div>
        </div>
      </div>
    );
  }

  if (!portfolio?.positions.length) {
    return (
      <div className="rounded-md border border-border bg-surface/50">
        <div className="flex h-64 items-center justify-center text-text-muted">
          No positions yet. Add your first position to get started.
        </div>
      </div>
    );
  }

  return (
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
          {table.getRowModel().rows.map((row) => (
            <TableRow key={row.id}>
              {row.getVisibleCells().map((cell) => (
                <TableCell key={cell.id}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
