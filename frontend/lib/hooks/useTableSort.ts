import { useState, useCallback } from "react";

export type SortDirection = "asc" | "desc";

interface UseTableSortResult<K extends string> {
  sortKey: K;
  sortDirection: SortDirection;
  toggleSort: (key: K) => void;
  setSortKey: (key: K) => void;
  setSortDirection: (direction: SortDirection) => void;
}

/**
 * Generic table sorting hook with toggle functionality.
 *
 * @param defaultKey - Initial sort key
 * @param defaultDirection - Initial sort direction (defaults to 'asc')
 * @returns Sort state and toggle function
 *
 * @example
 * const { sortKey, sortDirection, toggleSort } = useTableSort<'name' | 'date'>('name');
 *
 * // In table header:
 * <th onClick={() => toggleSort('name')}>Name</th>
 */
export function useTableSort<K extends string>(
  defaultKey: K,
  defaultDirection: SortDirection = "asc"
): UseTableSortResult<K> {
  const [sortKey, setSortKey] = useState<K>(defaultKey);
  const [sortDirection, setSortDirection] = useState<SortDirection>(defaultDirection);

  const toggleSort = useCallback((key: K) => {
    if (sortKey === key) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection("asc");
    }
  }, [sortKey]);

  return {
    sortKey,
    sortDirection,
    toggleSort,
    setSortKey,
    setSortDirection,
  };
}
