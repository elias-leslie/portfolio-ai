import type { WatchlistItem } from "@/lib/api/watchlist";

export type SortField =
  | "symbol"
  | "overall"
  | "price"
  | "technical"
  | "news"
  | "updated"
  | "risk";
export type SortDirection = "asc" | "desc";

/**
 * Sort watchlist items by the specified field and direction.
 */
export function sortWatchlistItems(
  items: WatchlistItem[],
  field: SortField,
  direction: SortDirection
): WatchlistItem[] {
  return [...items].sort((a, b) => {
    let aVal: string | number = "";
    let bVal: string | number = "";

    switch (field) {
      case "symbol":
        aVal = a.symbol;
        bVal = b.symbol;
        break;
      case "overall":
        aVal = a.currentScore?.overall ?? -1;
        bVal = b.currentScore?.overall ?? -1;
        break;
      case "price":
        aVal = a.currentScore?.price.score ?? -1;
        bVal = b.currentScore?.price.score ?? -1;
        break;
      case "technical":
        aVal = a.currentScore?.technical.score ?? -1;
        bVal = b.currentScore?.technical.score ?? -1;
        break;
      case "news":
        aVal = a.newsSentimentScore ?? -2;
        bVal = b.newsSentimentScore ?? -2;
        break;
      case "risk":
        aVal = a.riskLevel ?? "";
        bVal = b.riskLevel ?? "";
        break;
      case "updated":
        aVal = a.currentScore?.price?.updatedAt ?? a.updatedAt;
        bVal = b.currentScore?.price?.updatedAt ?? b.updatedAt;
        break;
    }

    if (typeof aVal === "string" && typeof bVal === "string") {
      return direction === "asc"
        ? aVal.localeCompare(bVal)
        : bVal.localeCompare(aVal);
    }

    return direction === "asc"
      ? (aVal as number) - (bVal as number)
      : (bVal as number) - (aVal as number);
  });
}
