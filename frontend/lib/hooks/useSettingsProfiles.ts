/**
 * React Query hooks for settings profiles
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { PreferencesResponse } from "@/lib/api/preferences";
import * as profilesApi from "@/lib/api/settings-profiles";

// Query Keys
export const profileKeys = {
  all: ["settings-profiles"] as const,
  lists: () => [...profileKeys.all, "list"] as const,
  list: (userId: number) => [...profileKeys.lists(), userId] as const,
  details: () => [...profileKeys.all, "detail"] as const,
  detail: (id: number) => [...profileKeys.details(), id] as const,
  active: (userId: number) => [...profileKeys.all, "active", userId] as const,
};

/**
 * Hook to fetch all profiles
 */
export function useProfiles(userId: number = 1) {
  return useQuery({
    queryKey: profileKeys.list(userId),
    queryFn: () => profilesApi.fetchProfiles(userId),
  });
}

/**
 * Hook to fetch active profile
 */
export function useActiveProfile(userId: number = 1) {
  return useQuery({
    queryKey: profileKeys.active(userId),
    queryFn: () => profilesApi.fetchActiveProfile(userId),
    retry: false, // Don't retry if no active profile
  });
}

/**
 * Hook to fetch a specific profile
 */
export function useProfile(profileId: number, userId: number = 1) {
  return useQuery({
    queryKey: profileKeys.detail(profileId),
    queryFn: () => profilesApi.fetchProfileById(profileId, userId),
    enabled: !!profileId,
  });
}

/**
 * Hook to create a profile
 */
export function useCreateProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      name: string;
      description?: string;
      profile_data: PreferencesResponse;
      is_active?: boolean;
      user_id?: number;
    }) => profilesApi.createProfile(data),
    onSuccess: (_, variables) => {
      const userId = variables.user_id || 1;
      queryClient.invalidateQueries({ queryKey: profileKeys.list(userId) });
      if (variables.is_active) {
        queryClient.invalidateQueries({ queryKey: profileKeys.active(userId) });
      }
    },
  });
}

/**
 * Hook to update a profile
 */
export function useUpdateProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      profileId,
      ...data
    }: {
      profileId: number;
      name?: string;
      description?: string;
      profile_data?: PreferencesResponse;
      is_active?: boolean;
      user_id?: number;
    }) => profilesApi.updateProfile(profileId, data),
    onSuccess: (data, variables) => {
      const userId = variables.user_id || 1;
      queryClient.invalidateQueries({ queryKey: profileKeys.list(userId) });
      queryClient.invalidateQueries({
        queryKey: profileKeys.detail(variables.profileId),
      });
      if (variables.is_active) {
        queryClient.invalidateQueries({ queryKey: profileKeys.active(userId) });
      }
    },
  });
}

/**
 * Hook to delete a profile
 */
export function useDeleteProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ profileId, userId = 1 }: { profileId: number; userId?: number }) =>
      profilesApi.deleteProfile(profileId, userId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: profileKeys.list(variables.userId || 1) });
      queryClient.invalidateQueries({
        queryKey: profileKeys.detail(variables.profileId),
      });
    },
  });
}

/**
 * Hook to activate a profile
 */
export function useActivateProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ profileId, userId = 1 }: { profileId: number; userId?: number }) =>
      profilesApi.activateProfile(profileId, userId),
    onSuccess: (_, variables) => {
      const userId = variables.userId || 1;
      queryClient.invalidateQueries({ queryKey: profileKeys.list(userId) });
      queryClient.invalidateQueries({ queryKey: profileKeys.active(userId) });
    },
  });
}

/**
 * Hook to duplicate a profile
 */
export function useDuplicateProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      profileId,
      newName,
      userId = 1,
    }: {
      profileId: number;
      newName: string;
      userId?: number;
    }) => profilesApi.duplicateProfile(profileId, newName, userId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: profileKeys.list(variables.userId || 1) });
    },
  });
}

/**
 * Hook to export a profile
 */
export function useExportProfile() {
  return useMutation({
    mutationFn: ({ profileId, userId = 1 }: { profileId: number; userId?: number }) =>
      profilesApi.exportProfile(profileId, userId),
  });
}

/**
 * Hook to import a profile
 */
export function useImportProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      name: string;
      description?: string;
      profile_data: PreferencesResponse;
      user_id?: number;
    }) => profilesApi.importProfile(data),
    onSuccess: (_, variables) => {
      const userId = variables.user_id || 1;
      queryClient.invalidateQueries({ queryKey: profileKeys.list(userId) });
    },
  });
}
