"use client";

import { useMemo } from "react";
import { SectionCard } from "@/components/shared/SectionCard";
import { cn } from "@/lib/utils";

interface EquityPoint {
  date: string;
  equity: string | number;
}

interface MonthlyReturnsHeatmapProps {
  equityCurve: EquityPoint[];
}

interface MonthlyReturn {
  year: number;
  month: number;
  monthName: string;
  returnPct: number;
}

const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
];

function calculateMonthlyReturns(equityCurve: EquityPoint[]): MonthlyReturn[] {
  if (!equityCurve || equityCurve.length < 2) return [];

  // Group equity points by year-month
  const monthlyData = new Map<string, { first: number; last: number }>();

  equityCurve.forEach((point) => {
    const date = new Date(point.date);
    const key = `${date.getFullYear()}-${date.getMonth()}`;
    const equity = typeof point.equity === "string" ? parseFloat(point.equity) : point.equity;

    if (!monthlyData.has(key)) {
      monthlyData.set(key, { first: equity, last: equity });
    } else {
      const data = monthlyData.get(key)!;
      data.last = equity;
    }
  });

  // Calculate returns
  const returns: MonthlyReturn[] = [];
  monthlyData.forEach((data, key) => {
    const [yearStr, monthStr] = key.split("-");
    const year = parseInt(yearStr);
    const month = parseInt(monthStr);
    const returnPct = ((data.last - data.first) / data.first) * 100;

    returns.push({
      year,
      month,
      monthName: MONTH_NAMES[month],
      returnPct,
    });
  });

  // Sort by date
  returns.sort((a, b) => {
    if (a.year !== b.year) return a.year - b.year;
    return a.month - b.month;
  });

  return returns;
}

function getColorClass(returnPct: number): string {
  if (returnPct >= 10) return "bg-status-success text-white";
  if (returnPct >= 5) return "bg-status-success/80 text-white";
  if (returnPct >= 2) return "bg-status-success/60 text-white";
  if (returnPct >= 0) return "bg-status-success/20 text-status-success";
  if (returnPct >= -2) return "bg-status-error/20 text-status-error";
  if (returnPct >= -5) return "bg-status-error/60 text-white";
  if (returnPct >= -10) return "bg-status-error/80 text-white";
  return "bg-status-error text-white";
}

export function MonthlyReturnsHeatmap({ equityCurve }: MonthlyReturnsHeatmapProps) {
  const monthlyReturns = useMemo(
    () => calculateMonthlyReturns(equityCurve),
    [equityCurve]
  );

  if (monthlyReturns.length === 0) {
    return null;
  }

  // Get unique years
  const years = [...new Set(monthlyReturns.map((r) => r.year))].sort();

  // Create a lookup map for quick access
  const returnLookup = new Map(
    monthlyReturns.map((r) => [`${r.year}-${r.month}`, r.returnPct])
  );

  // Calculate yearly totals
  const yearlyTotals = years.map((year) => {
    const yearReturns = monthlyReturns.filter((r) => r.year === year);
    // Compound returns
    let compounded = 1;
    yearReturns.forEach((r) => {
      compounded *= 1 + r.returnPct / 100;
    });
    return { year, total: (compounded - 1) * 100 };
  });

  return (
    <SectionCard
      variant="surface"
      title="Monthly Returns Heatmap"
      description="Performance breakdown by month with color-coded returns"
    >
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr>
              <th className="px-2 py-1 text-left text-text-muted font-medium">Year</th>
              {MONTH_NAMES.map((month) => (
                <th key={month} className="px-2 py-1 text-center text-text-muted font-medium">
                  {month}
                </th>
              ))}
              <th className="px-2 py-1 text-center text-text-muted font-medium">Total</th>
            </tr>
          </thead>
          <tbody>
            {years.map((year) => {
              const yearTotal = yearlyTotals.find((y) => y.year === year);
              return (
                <tr key={year}>
                  <td className="px-2 py-1 font-medium text-text">{year}</td>
                  {MONTH_NAMES.map((_, monthIdx) => {
                    const key = `${year}-${monthIdx}`;
                    const returnPct = returnLookup.get(key);

                    if (returnPct === undefined) {
                      return (
                        <td key={key} className="px-1 py-1">
                          <div className="h-8 w-full rounded bg-surface-muted/30" />
                        </td>
                      );
                    }

                    return (
                      <td key={key} className="px-1 py-1">
                        <div
                          className={cn(
                            "h-8 w-full rounded flex items-center justify-center font-medium",
                            getColorClass(returnPct)
                          )}
                          title={`${MONTH_NAMES[monthIdx]} ${year}: ${returnPct >= 0 ? "+" : ""}${returnPct.toFixed(2)}%`}
                        >
                          {returnPct >= 0 ? "+" : ""}{returnPct.toFixed(1)}%
                        </div>
                      </td>
                    );
                  })}
                  <td className="px-1 py-1">
                    <div
                      className={cn(
                        "h-8 w-full rounded flex items-center justify-center font-bold",
                        yearTotal ? getColorClass(yearTotal.total) : "bg-surface-muted/30"
                      )}
                    >
                      {yearTotal
                        ? `${yearTotal.total >= 0 ? "+" : ""}${yearTotal.total.toFixed(1)}%`
                        : "—"}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-4 text-xs text-text-muted text-center">
        Green = positive returns • Red = negative returns • Darker = larger magnitude
      </p>
    </SectionCard>
  );
}
