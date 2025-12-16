"use client";

import { useMemo } from "react";
import { useMarketEvents } from "@/lib/hooks/useMarketIntelligence";
import { MarketEvent } from "@/lib/api/market";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface EventTimelineProps {
  days: number;
  className?: string;
}

interface EventMarkerProps {
  event: MarketEvent;
  position: number; // 0-100 percentage position
}

function EventMarker({ event, position }: EventMarkerProps) {
  const formatEventDate = (dateStr: string) => {
    const date = new Date(dateStr + "T12:00:00");
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  return (
    <TooltipProvider delayDuration={100}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className="absolute top-0 bottom-0 w-px cursor-pointer group z-10"
            style={{ left: `${position}%` }}
          >
            {/* Vertical line */}
            <div
              className="absolute top-0 bottom-0 w-px opacity-40 group-hover:opacity-80 transition-opacity"
              style={{ backgroundColor: event.color }}
            />
            {/* Event marker dot */}
            <div
              className="absolute -top-1 -translate-x-1/2 w-3 h-3 rounded-full border-2 border-surface-card shadow-sm group-hover:scale-125 transition-transform"
              style={{ backgroundColor: event.color }}
            />
          </div>
        </TooltipTrigger>
        <TooltipContent
          side="top"
          className="bg-surface-card border border-border-subtle p-3 max-w-xs"
        >
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span
                className="px-1.5 py-0.5 text-xs font-medium rounded"
                style={{
                  backgroundColor: event.color + "20",
                  color: event.color,
                }}
              >
                {event.label}
              </span>
              <span className="text-xs text-text-muted">
                {formatEventDate(event.date)}
              </span>
            </div>
            <p className="text-sm font-medium text-text-primary">
              {event.title}
            </p>
            {(event.actualValue !== null || event.expectedValue !== null) && (
              <div className="flex gap-3 text-xs">
                {event.expectedValue !== null && (
                  <span className="text-text-muted">
                    Est: {event.expectedValue.toFixed(2)}
                  </span>
                )}
                {event.actualValue !== null && (
                  <span className="text-text-primary">
                    Act: {event.actualValue.toFixed(2)}
                  </span>
                )}
                {event.surprisePct !== null && (
                  <span
                    className={cn(
                      event.surprisePct > 0
                        ? "text-success"
                        : event.surprisePct < 0
                          ? "text-error"
                          : "text-text-muted"
                    )}
                  >
                    {event.surprisePct > 0 ? "+" : ""}
                    {event.surprisePct.toFixed(1)}%
                  </span>
                )}
              </div>
            )}
            {event.impactScore !== null && (
              <div className="text-xs text-text-muted">
                Impact:{" "}
                <span
                  className={cn(
                    event.impactScore > 0
                      ? "text-success"
                      : event.impactScore < 0
                        ? "text-error"
                        : "text-text-muted"
                  )}
                >
                  {event.impactScore > 0 ? "+" : ""}
                  {event.impactScore}
                </span>
              </div>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

/**
 * EventTimeline - Shows market events (FOMC, CPI, NFP) as vertical markers
 *
 * Designed to overlay on top of sentiment/indicator charts.
 * Position absolutely within a relative container.
 */
export function EventTimeline({ days, className }: EventTimelineProps) {
  const { data: eventsData, isLoading } = useMarketEvents(days);

  const eventsWithPosition = useMemo(() => {
    if (!eventsData?.events?.length) return [];

    const now = Date.now();
    const startTime = now - days * 24 * 60 * 60 * 1000;
    const totalRange = now - startTime;

    return eventsData.events
      .map((event) => {
        const eventTime = new Date(event.date + "T12:00:00").getTime();
        // Only include events within our date range
        if (eventTime < startTime || eventTime > now) return null;

        const position = ((eventTime - startTime) / totalRange) * 100;
        return { event, position };
      })
      .filter(Boolean) as { event: MarketEvent; position: number }[];
  }, [eventsData, days]);

  if (isLoading || !eventsWithPosition.length) {
    return null;
  }

  return (
    <div className={cn("absolute inset-0 pointer-events-none", className)}>
      {eventsWithPosition.map(({ event, position }) => (
        <div key={event.id} className="pointer-events-auto">
          <EventMarker event={event} position={position} />
        </div>
      ))}
    </div>
  );
}

/**
 * EventLegend - Shows legend for event types
 */
export function EventLegend({ className }: { className?: string }) {
  const eventTypes = [
    { label: "FOMC", color: "#3B82F6" },
    { label: "CPI", color: "#EF4444" },
    { label: "NFP", color: "#22C55E" },
    { label: "GDP", color: "#06B6D4" },
  ];

  return (
    <div className={cn("flex items-center gap-3 text-xs", className)}>
      <span className="text-text-muted">Events:</span>
      {eventTypes.map((type) => (
        <div key={type.label} className="flex items-center gap-1">
          <div
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: type.color }}
          />
          <span className="text-text-muted">{type.label}</span>
        </div>
      ))}
    </div>
  );
}
