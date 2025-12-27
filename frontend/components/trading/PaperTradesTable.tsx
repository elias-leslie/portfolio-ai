"use client";

import { Fragment, useState } from "react";
import { ChevronDown, ChevronRight, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ConfirmActionDialog } from "@/components/shared/ConfirmActionDialog";
import { useClosePaperTrade } from "@/lib/hooks/usePaperTrades";
import { type PaperTrade } from "@/lib/api/paper-trades";
import { TradeDetails } from "./TradeDetails";

interface PaperTradesTableProps {
  trades: PaperTrade[];
  type: "open" | "closed";
}

export function PaperTradesTable({ trades, type }: PaperTradesTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [closeDialogOpen, setCloseDialogOpen] = useState(false);
  const [selectedTrade, setSelectedTrade] = useState<PaperTrade | null>(null);

  const closeTrade = useClosePaperTrade();

  // Toggle row expansion
  const toggleRow = (tradeId: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(tradeId)) {
        next.delete(tradeId);
      } else {
        next.add(tradeId);
      }
      return next;
    });
  };

  // Handle close trade
  const handleCloseTrade = (trade: PaperTrade) => {
    setSelectedTrade(trade);
    setCloseDialogOpen(true);
  };

  const confirmCloseTrade = () => {
    if (!selectedTrade) return;

    closeTrade.mutate(
      { tradeId: selectedTrade.ideaId, request: { exitReason: "manual" } },
      {
        onSuccess: () => {
          setCloseDialogOpen(false);
          setSelectedTrade(null);
        },
      }
    );
  };

  // Format helpers
  const formatPrice = (price: number | undefined) => {
    if (price === undefined || price === null) return "-";
    return `$${price.toFixed(2)}`;
  };

  const formatPct = (value: number | undefined) => {
    if (value === undefined || value === null) return "-";
    return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
  };

  const getPnlColor = (value: number | undefined) => {
    if (!value) return "";
    return value >= 0 ? "text-gain" : "text-loss";
  };

  const formatPnlDollars = (trade: PaperTrade, isClosed: boolean) => {
    const shares = trade.shares || 0;
    const entryPrice = trade.entryPrice || 0;
    const exitPrice = isClosed ? (trade.exitPrice || 0) : (trade.currentPrice || 0);
    if (shares === 0 || entryPrice === 0) return "-";
    const pnl = (exitPrice - entryPrice) * shares;
    const prefix = pnl >= 0 ? "+$" : "-$";
    return `${prefix}${Math.abs(pnl).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };


  return (
    <>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12"></TableHead>
              <TableHead>Symbol</TableHead>
              <TableHead>Type</TableHead>
              <TableHead className="text-right">Shares</TableHead>
              <TableHead className="text-right">Entry</TableHead>
              {type === "open" && (
                <>
                  <TableHead className="text-right">Current</TableHead>
                  <TableHead className="text-right">P&L $</TableHead>
                  <TableHead className="text-right">P&L %</TableHead>
                  <TableHead className="text-right">Target</TableHead>
                  <TableHead className="text-right">Stop</TableHead>
                  <TableHead className="text-center">Days</TableHead>
                </>
              )}
              {type === "closed" && (
                <>
                  <TableHead className="text-right">Exit</TableHead>
                  <TableHead className="text-right">P&L $</TableHead>
                  <TableHead className="text-right">P&L %</TableHead>
                  <TableHead className="text-center">Days Held</TableHead>
                  <TableHead>Exit Reason</TableHead>
                </>
              )}
              {type === "open" && <TableHead className="text-right">Actions</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {trades.map((trade) => {
              const isExpanded = expandedRows.has(trade.ideaId);
              const pnlPct =
                type === "open" ? trade.currentReturnPct : trade.realizedReturnPct;
              const pnlDollars = (() => {
                const shares = trade.shares || 0;
                const entryPrice = trade.entryPrice || 0;
                const exitPrice = type === "closed" ? (trade.exitPrice || 0) : (trade.currentPrice || 0);
                return shares > 0 && entryPrice > 0 ? (exitPrice - entryPrice) * shares : 0;
              })();

              return (
                <Fragment key={trade.ideaId}>
                  {/* Main Row */}
                  <TableRow
                    className="cursor-pointer hover:bg-surface-muted/50"
                    onClick={() => toggleRow(trade.ideaId)}
                  >
                    <TableCell>
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                      </Button>
                    </TableCell>
                    <TableCell className="font-semibold">{trade.symbol}</TableCell>
                    <TableCell>
                      <Badge variant={trade.ideaType === "buy" ? "default" : "secondary"}>
                        {trade.ideaType.toUpperCase()}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">{trade.shares || "-"}</TableCell>
                    <TableCell className="text-right">{formatPrice(trade.entryPrice)}</TableCell>
                    {type === "open" && (
                      <>
                        <TableCell className="text-right">
                          {formatPrice(trade.currentPrice)}
                        </TableCell>
                        <TableCell className={`text-right font-semibold ${getPnlColor(pnlDollars)}`}>
                          {formatPnlDollars(trade, false)}
                        </TableCell>
                        <TableCell className={`text-right font-semibold ${getPnlColor(pnlPct)}`}>
                          {formatPct(pnlPct)}
                        </TableCell>
                        <TableCell className="text-right text-text-muted">
                          {formatPrice(trade.targetPrice)}
                        </TableCell>
                        <TableCell className="text-right text-text-muted">
                          {formatPrice(trade.stopLossPrice)}
                        </TableCell>
                        <TableCell className="text-center text-text-muted">
                          {trade.holdingDays || 0}
                        </TableCell>
                      </>
                    )}
                    {type === "closed" && (
                      <>
                        <TableCell className="text-right">{formatPrice(trade.exitPrice)}</TableCell>
                        <TableCell className={`text-right font-semibold ${getPnlColor(pnlDollars)}`}>
                          {formatPnlDollars(trade, true)}
                        </TableCell>
                        <TableCell className={`text-right font-semibold ${getPnlColor(pnlPct)}`}>
                          {formatPct(pnlPct)}
                        </TableCell>
                        <TableCell className="text-center text-text-muted">
                          {trade.holdingDays || 0}
                        </TableCell>
                        <TableCell className="text-text-muted">
                          {trade.exitReason || "-"}
                        </TableCell>
                      </>
                    )}
                    {type === "open" && (
                      <TableCell
                        className="text-right"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleCloseTrade(trade)}
                          disabled={closeTrade.isPending}
                        >
                          <X className="mr-1 h-4 w-4" />
                          Close
                        </Button>
                      </TableCell>
                    )}
                  </TableRow>

                  {/* Expanded Row Details */}
                  {isExpanded && (
                    <TableRow>
                      <TableCell colSpan={type === "open" ? 12 : 11} className="bg-surface-muted/30">
                        <TradeDetails trade={trade} />
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {/* Close Trade Confirmation Dialog */}
      <ConfirmActionDialog
        open={closeDialogOpen}
        onOpenChange={setCloseDialogOpen}
        onConfirm={confirmCloseTrade}
        title={`Close ${selectedTrade?.symbol} Trade?`}
        description={`This will close your ${selectedTrade?.ideaType} position in ${selectedTrade?.symbol} at the current market price. Current P&L: ${formatPct(selectedTrade?.currentReturnPct)}`}
        confirmLabel="Close Position"
        tone="default"
      />
    </>
  );
}
