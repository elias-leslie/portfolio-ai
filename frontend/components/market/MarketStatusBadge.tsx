"use client";

import { useQuery } from "@tanstack/react-query";
import { Clock } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { apiRequest } from "@/lib/api/client";
import { cn } from "@/lib/utils";

interface MarketStatusResponse {
  status: "open" | "pre_market" | "after_hours" | "closed";
  is_open: boolean;
  last_trading_day: string;
  next_trading_day: string;
  current_time_et: string;
  is_holiday: boolean;
  holiday_name: string | null;
  is_early_close: boolean;
  early_close_name: string | null;
}

async function fetchMarketStatus(): Promise<MarketStatusResponse> {
  return apiRequest<MarketStatusResponse>("/api/market/status");
}

const STATUS_CONFIG = {
  open: {
    label: "Market Open",
    dotColor: "bg-success",
    badgeVariant: "success" as const,
  },
  pre_market: {
    label: "Pre-Market",
    dotColor: "bg-warning",
    badgeVariant: "warning" as const,
  },
  after_hours: {
    label: "After Hours",
    dotColor: "bg-warning",
    badgeVariant: "warning" as const,
  },
  closed: {
    label: "Market Closed",
    dotColor: "bg-text-muted",
    badgeVariant: "secondary" as const,
  },
};

export function MarketStatusBadge() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["market-status"],
    queryFn: fetchMarketStatus,
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: 30 * 1000, // Refresh every 30 seconds
    refetchOnWindowFocus: true,
  });

  if (isLoading) {
    return (
      <Badge variant="secondary" className="gap-1.5 px-2 py-1">
        <Clock className="size-3 animate-pulse" />
        <span className="hidden sm:inline">Loading...</span>
      </Badge>
    );
  }

  if (error || !data) {
    return (
      <Badge variant="secondary" className="gap-1.5 px-2 py-1">
        <div className="size-2 rounded-full bg-text-muted" />
        <span className="hidden sm:inline">Unknown</span>
      </Badge>
    );
  }

  const config = STATUS_CONFIG[data.status];

  // Build tooltip content
  const tooltipLines: string[] = [];
  tooltipLines.push(`Current: ${data.current_time_et}`);
  tooltipLines.push(`Last Trading: ${data.last_trading_day}`);
  tooltipLines.push(`Next Trading: ${data.next_trading_day}`);
  if (data.is_holiday && data.holiday_name) {
    tooltipLines.push(`Holiday: ${data.holiday_name}`);
  }
  if (data.is_early_close && data.early_close_name) {
    tooltipLines.push(`Early Close: ${data.early_close_name}`);
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge
            variant={config.badgeVariant}
            className="cursor-help gap-1.5 px-2 py-1"
          >
            <div
              className={cn(
                "size-2 rounded-full",
                config.dotColor,
                data.status === "open" && "animate-pulse"
              )}
            />
            <span className="hidden sm:inline">{config.label}</span>
          </Badge>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="max-w-xs">
          <div className="space-y-1 text-xs">
            {tooltipLines.map((line, i) => (
              <p key={i}>{line}</p>
            ))}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
