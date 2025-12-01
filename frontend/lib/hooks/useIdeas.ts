/**
 * React Query hooks for Ideas API
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  GenerateIdeasRequest,
  UpdateIdeaStatusRequest,
  fetchIdeaDetails,
  fetchIdeas,
  generateIdeas,
  updateIdeaStatus,
} from "../api/ideas";

/**
 * Hook to fetch investment ideas with optional filtering
 */
export function useIdeas(params?: {
  idea_type?: string;
  status?: string;
  limit?: number;
}) {
  return useQuery({
    queryKey: ["ideas", params],
    queryFn: () => fetchIdeas(params),
    staleTime: 1000 * 60 * 2, // 2 minutes
  });
}

/**
 * Hook to generate new investment ideas by running an agent
 */
export function useGenerateIdeas() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: GenerateIdeasRequest) => generateIdeas(data),
    onSuccess: () => {
      // Invalidate ideas query to refetch with new ideas
      queryClient.invalidateQueries({ queryKey: ["ideas"] });
    },
  });
}

/**
 * Hook to fetch detailed information about a specific idea
 */
export function useIdeaDetails(ideaId: string | null) {
  return useQuery({
    queryKey: ["ideas", ideaId],
    queryFn: () => (ideaId ? fetchIdeaDetails(ideaId) : null),
    enabled: !!ideaId, // Only run if ideaId is provided
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: false, // Don't retry on 404 - show "not found" immediately
  });
}

/**
 * Hook to update the status of an investment idea
 */
export function useUpdateIdeaStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      ideaId,
      data,
    }: {
      ideaId: string;
      data: UpdateIdeaStatusRequest;
    }) => {
      const promise = updateIdeaStatus(ideaId, data);

      // Create human-readable status labels
      const statusLabels: Record<string, string> = {
        pending: "Pending",
        validated: "Validated",
        executed: "Executed",
        rejected: "Rejected",
      };
      const statusLabel = statusLabels[data.status] || data.status;

      toast.promise(promise, {
        loading: `Updating idea status...`,
        success: `Idea status updated to ${statusLabel}`,
        error: (error) => {
          const errorMsg = error instanceof Error ? error.message : "Failed to update status";
          return `Failed to update idea: ${errorMsg}`;
        },
      });
      return promise;
    },
    onSuccess: (_, variables) => {
      // Invalidate both the list and the specific idea detail
      queryClient.invalidateQueries({ queryKey: ["ideas"] });
      queryClient.invalidateQueries({ queryKey: ["ideas", variables.ideaId] });
    },
  });
}
