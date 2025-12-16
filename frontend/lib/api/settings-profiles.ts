/**
 * API client for settings profiles
 */

import type { PreferencesResponse } from "./preferences";

export interface SettingsProfile {
  id: number;
  userId: number;
  name: string;
  description: string | null;
  profileData: PreferencesResponse;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface ProfileExport {
  name: string;
  description: string | null;
  profileData: PreferencesResponse;
  exportedAt: string;
  version: string;
}

const API_BASE_URL = ""; // Use relative URLs for Next.js proxy

/**
 * Fetch all profiles
 */
export async function fetchProfiles(userId: number = 1): Promise<SettingsProfile[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/settings/profiles?user_id=${userId}`
  );
  if (!response.ok) {
    throw new Error("Failed to fetch profiles");
  }
  return response.json();
}

/**
 * Fetch active profile
 */
export async function fetchActiveProfile(userId: number = 1): Promise<SettingsProfile> {
  const response = await fetch(
    `${API_BASE_URL}/api/settings/profiles/active?user_id=${userId}`
  );
  if (!response.ok) {
    throw new Error("Failed to fetch active profile");
  }
  return response.json();
}

/**
 * Fetch a specific profile by ID
 */
export async function fetchProfileById(
  profileId: number,
  userId: number = 1
): Promise<SettingsProfile> {
  const response = await fetch(
    `${API_BASE_URL}/api/settings/profiles/${profileId}?user_id=${userId}`
  );
  if (!response.ok) {
    throw new Error("Failed to fetch profile");
  }
  return response.json();
}

/**
 * Create a new profile
 */
export async function createProfile(data: {
  name: string;
  description?: string;
  profileData: PreferencesResponse;
  isActive?: boolean;
  userId?: number;
}): Promise<SettingsProfile> {
  const response = await fetch(`${API_BASE_URL}/api/settings/profiles`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      name: data.name,
      description: data.description,
      profile_data: data.profileData,
      is_active: data.isActive,
      user_id: data.userId || 1,
    }),
  });
  if (!response.ok) {
    throw new Error("Failed to create profile");
  }
  return response.json();
}

/**
 * Update an existing profile
 */
export async function updateProfile(
  profileId: number,
  data: {
    name?: string;
    description?: string;
    profileData?: PreferencesResponse;
    isActive?: boolean;
    userId?: number;
  }
): Promise<SettingsProfile> {
  const response = await fetch(
    `${API_BASE_URL}/api/settings/profiles/${profileId}`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: data.name,
        description: data.description,
        profile_data: data.profileData,
        is_active: data.isActive,
        user_id: data.userId || 1,
      }),
    }
  );
  if (!response.ok) {
    throw new Error("Failed to update profile");
  }
  return response.json();
}

/**
 * Delete a profile
 */
export async function deleteProfile(
  profileId: number,
  userId: number = 1
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/settings/profiles/${profileId}?user_id=${userId}`,
    {
      method: "DELETE",
    }
  );
  if (!response.ok) {
    throw new Error("Failed to delete profile");
  }
}

/**
 * Activate a profile
 */
export async function activateProfile(
  profileId: number,
  userId: number = 1
): Promise<SettingsProfile> {
  const response = await fetch(
    `${API_BASE_URL}/api/settings/profiles/${profileId}/activate?user_id=${userId}`,
    {
      method: "POST",
    }
  );
  if (!response.ok) {
    throw new Error("Failed to activate profile");
  }
  return response.json();
}

/**
 * Duplicate a profile
 */
export async function duplicateProfile(
  profileId: number,
  newName: string,
  userId: number = 1
): Promise<SettingsProfile> {
  const response = await fetch(
    `${API_BASE_URL}/api/settings/profiles/${profileId}/duplicate`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: newName,
        user_id: userId,
      }),
    }
  );
  if (!response.ok) {
    throw new Error("Failed to duplicate profile");
  }
  return response.json();
}

/**
 * Export a profile
 */
export async function exportProfile(
  profileId: number,
  userId: number = 1
): Promise<ProfileExport> {
  const response = await fetch(
    `${API_BASE_URL}/api/settings/profiles/${profileId}/export?user_id=${userId}`
  );
  if (!response.ok) {
    throw new Error("Failed to export profile");
  }
  return response.json();
}

/**
 * Import a profile
 */
export async function importProfile(data: {
  name: string;
  description?: string;
  profileData: PreferencesResponse;
  userId?: number;
}): Promise<SettingsProfile> {
  const response = await fetch(`${API_BASE_URL}/api/settings/profiles/import`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      name: data.name,
      description: data.description,
      profile_data: data.profileData,
      user_id: data.userId || 1,
    }),
  });
  if (!response.ok) {
    throw new Error("Failed to import profile");
  }
  return response.json();
}
