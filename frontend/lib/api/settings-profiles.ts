/**
 * API client for settings profiles
 */

import { del, get, post, put } from './client'
import type { PreferencesResponse } from './preferences'

export interface SettingsProfile {
  id: number
  userId: number
  name: string
  description: string | null
  profileData: PreferencesResponse
  isActive: boolean
  createdAt: string
  updatedAt: string
}

export interface ProfileExport {
  name: string
  description: string | null
  profileData: PreferencesResponse
  exportedAt: string
  version: string
}

/**
 * Fetch all profiles
 */
export async function fetchProfiles(
  userId: number = 1,
): Promise<SettingsProfile[]> {
  return get<SettingsProfile[]>(`/api/settings/profiles?user_id=${userId}`)
}

/**
 * Fetch active profile
 */
export async function fetchActiveProfile(
  userId: number = 1,
): Promise<SettingsProfile> {
  return get<SettingsProfile>(`/api/settings/profiles/active?user_id=${userId}`)
}

/**
 * Fetch a specific profile by ID
 */
export async function fetchProfileById(
  profileId: number,
  userId: number = 1,
): Promise<SettingsProfile> {
  return get<SettingsProfile>(
    `/api/settings/profiles/${profileId}?user_id=${userId}`,
  )
}

/**
 * Create a new profile
 */
export async function createProfile(data: {
  name: string
  description?: string
  profileData: PreferencesResponse
  isActive?: boolean
  userId?: number
}): Promise<SettingsProfile> {
  return post<SettingsProfile>('/api/settings/profiles', {
    name: data.name,
    description: data.description,
    profileData: data.profileData,
    isActive: data.isActive,
    userId: data.userId || 1,
  })
}

/**
 * Update an existing profile
 */
export async function updateProfile(
  profileId: number,
  data: {
    name?: string
    description?: string
    profileData?: PreferencesResponse
    isActive?: boolean
    userId?: number
  },
): Promise<SettingsProfile> {
  return put<SettingsProfile>(`/api/settings/profiles/${profileId}`, {
    name: data.name,
    description: data.description,
    profileData: data.profileData,
    isActive: data.isActive,
    userId: data.userId || 1,
  })
}

/**
 * Delete a profile
 */
export async function deleteProfile(
  profileId: number,
  userId: number = 1,
): Promise<void> {
  await del<void>(`/api/settings/profiles/${profileId}?user_id=${userId}`)
}

/**
 * Activate a profile
 */
export async function activateProfile(
  profileId: number,
  userId: number = 1,
): Promise<SettingsProfile> {
  return post<SettingsProfile>(
    `/api/settings/profiles/${profileId}/activate?user_id=${userId}`,
  )
}

/**
 * Duplicate a profile
 */
export async function duplicateProfile(
  profileId: number,
  newName: string,
  userId: number = 1,
): Promise<SettingsProfile> {
  return post<SettingsProfile>(
    `/api/settings/profiles/${profileId}/duplicate`,
    {
      name: newName,
      userId,
    },
  )
}

/**
 * Export a profile
 */
export async function exportProfile(
  profileId: number,
  userId: number = 1,
): Promise<ProfileExport> {
  return get<ProfileExport>(
    `/api/settings/profiles/${profileId}/export?user_id=${userId}`,
  )
}

/**
 * Import a profile
 */
export async function importProfile(data: {
  name: string
  description?: string
  profileData: PreferencesResponse
  userId?: number
}): Promise<SettingsProfile> {
  return post<SettingsProfile>('/api/settings/profiles/import', {
    name: data.name,
    description: data.description,
    profileData: data.profileData,
    userId: data.userId || 1,
  })
}
