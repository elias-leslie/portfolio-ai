/**
 * React Query hook for Solution Map data
 */

import { useQuery } from "@tanstack/react-query";
import { fetchSolutionMap, SolutionMapResponse } from "../api/solutionMap";

export function useSolutionMap() {
  return useQuery<SolutionMapResponse>({
    queryKey: ["solution-map"],
    queryFn: fetchSolutionMap,
    staleTime: 60_000, // 1 minute
    gcTime: 5 * 60_000, // 5 minutes
    refetchOnWindowFocus: false,
    retry: 1,
  });
}
