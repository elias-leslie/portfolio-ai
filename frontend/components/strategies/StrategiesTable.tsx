"use client";

import { formatDistanceToNow } from "date-fns";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { StrategyListItem } from "@/lib/api/strategies";

interface StrategiesTableProps {
  strategies: StrategyListItem[];
  isLoading: boolean;
  onSelectStrategy: (strategyId: string) => void;
}

const strategyTypeColors: Record<string, string> = {
  momentum: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  value: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  event: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  reversal: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
  defensive: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
};

const statusColors: Record<string, string> = {
  testing: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  active: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  archived: "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400",
};

export function StrategiesTable({
  strategies,
  isLoading,
  onSelectStrategy,
}: StrategiesTableProps) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {[...Array(5)].map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (strategies.length === 0) {
    return (
      <div className="py-8 text-center text-text-muted">
        <p>No strategies found.</p>
        <p className="text-sm">Click &quot;Generate Strategies&quot; to create new strategies.</p>
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Symbol</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Expected Sharpe</TableHead>
            <TableHead className="text-right">Live Sharpe</TableHead>
            <TableHead className="text-right">Win Rate</TableHead>
            <TableHead className="text-right">Trades</TableHead>
            <TableHead>Created</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {strategies.map((strategy) => (
            <TableRow
              key={strategy.id}
              className="cursor-pointer hover:bg-muted/50"
              onClick={() => onSelectStrategy(strategy.id)}
            >
              <TableCell className="font-medium">{strategy.symbol}</TableCell>
              <TableCell className="max-w-[200px] truncate" title={strategy.name}>
                {strategy.name}
              </TableCell>
              <TableCell>
                <Badge
                  variant="outline"
                  className={strategyTypeColors[strategy.strategyType] || ""}
                >
                  {strategy.strategyType}
                </Badge>
              </TableCell>
              <TableCell>
                <Badge variant="outline" className={statusColors[strategy.status] || ""}>
                  {strategy.status}
                </Badge>
              </TableCell>
              <TableCell className="text-right">
                {strategy.expectedSharpe?.toFixed(2) || "-"}
              </TableCell>
              <TableCell className="text-right">
                {strategy.liveSharpeRatio?.toFixed(2) || "-"}
              </TableCell>
              <TableCell className="text-right">
                {strategy.liveWinRate != null
                  ? `${(strategy.liveWinRate * 100).toFixed(0)}%`
                  : "-"}
              </TableCell>
              <TableCell className="text-right">{strategy.tradesCount || 0}</TableCell>
              <TableCell className="text-text-muted">
                {formatDistanceToNow(new Date(strategy.createdAt), { addSuffix: true })}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
