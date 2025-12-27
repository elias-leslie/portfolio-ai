"use client";

import { useState, type ReactNode } from "react";
import { Save, Download, Upload, Copy, Trash2, Check } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import {
  useProfiles,
  useCreateProfile,
  useDeleteProfile,
  useActivateProfile,
  useDuplicateProfile,
  useExportProfile,
  useImportProfile,
} from "@/lib/hooks/useSettingsProfiles";
import type { PreferencesResponse } from "@/lib/api/preferences";
import { cn } from "@/lib/utils";

// Wrapper component extracted to avoid recreation during render
function ProfileSelectorWrapper({
  variant,
  className,
  children,
}: {
  variant: "card" | "plain";
  className?: string;
  children: ReactNode;
}) {
  return variant === "card" ? (
    <Card className={className}>
      <CardContent className="space-y-4 pt-6">{children}</CardContent>
    </Card>
  ) : (
    <div className={cn("space-y-4", className)}>{children}</div>
  );
}

interface ProfileSelectorProps {
  currentPreferences: PreferencesResponse;
  onProfileLoad: (preferences: PreferencesResponse) => void;
  userId?: number;
  variant?: "card" | "plain";
  className?: string;
}

export function ProfileSelector({
  currentPreferences,
  onProfileLoad,
  userId = 1,
  variant = "card",
  className,
}: ProfileSelectorProps) {
  const { data: profiles = [], isLoading } = useProfiles(userId);
  const createProfile = useCreateProfile();
  const deleteProfile = useDeleteProfile();
  const activateProfile = useActivateProfile();
  const duplicateProfile = useDuplicateProfile();
  const exportProfile = useExportProfile();
  const importProfile = useImportProfile();

  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [showDuplicateDialog, setShowDuplicateDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  const [saveName, setSaveName] = useState("");
  const [saveDescription, setSaveDescription] = useState("");
  const [duplicateProfileId, setDuplicateProfileId] = useState<number | null>(null);
  const [duplicateName, setDuplicateName] = useState("");
  const [deleteProfileId, setDeleteProfileId] = useState<number | null>(null);
  const [importData, setImportData] = useState("");

  const activeProfile = profiles.find((p) => p.isActive);

  const handleSave = async () => {
    if (!saveName.trim()) {
      toast.error("Please enter a profile name");
      return;
    }

    try {
      await createProfile.mutateAsync({
        name: saveName,
        description: saveDescription || undefined,
        profileData: currentPreferences,
        isActive: false,
        userId: userId,
      });
      toast.success(`Profile "${saveName}" saved successfully`);
      setShowSaveDialog(false);
      setSaveName("");
      setSaveDescription("");
    } catch {
      toast.error("Failed to save profile");
    }
  };

  const handleLoad = async (profileId: number) => {
    const profile = profiles.find((p) => p.id === profileId);
    if (!profile) return;

    try {
      onProfileLoad(profile.profileData);
      await activateProfile.mutateAsync({ profileId, userId });
      toast.success(`Profile "${profile.name}" loaded`);
    } catch {
      toast.error("Failed to load profile");
    }
  };

  const handleExport = async (profileId: number) => {
    const profile = profiles.find((p) => p.id === profileId);
    if (!profile) return;

    try {
      const exportData = await exportProfile.mutateAsync({ profileId, userId });
      const blob = new Blob([JSON.stringify(exportData, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${profile.name.replace(/\s+/g, "-").toLowerCase()}-profile.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success("Profile exported");
    } catch {
      toast.error("Failed to export profile");
    }
  };

  const handleImport = async () => {
    if (!importData.trim()) {
      toast.error("Please paste profile data");
      return;
    }

    try {
      const data = JSON.parse(importData);
      await importProfile.mutateAsync({
        name: data.name || "Imported Profile",
        description: data.description,
        profileData: data.profileData,
        userId: userId,
      });
      toast.success("Profile imported successfully");
      setShowImportDialog(false);
      setImportData("");
    } catch {
      toast.error("Failed to import profile. Check the JSON format.");
    }
  };

  const handleDuplicate = async () => {
    if (!duplicateProfileId || !duplicateName.trim()) {
      toast.error("Please enter a name for the duplicate");
      return;
    }

    try {
      await duplicateProfile.mutateAsync({
        profileId: duplicateProfileId,
        newName: duplicateName,
        userId,
      });
      toast.success("Profile duplicated successfully");
      setShowDuplicateDialog(false);
      setDuplicateProfileId(null);
      setDuplicateName("");
    } catch {
      toast.error("Failed to duplicate profile");
    }
  };

  const handleDelete = async () => {
    if (!deleteProfileId) return;

    const profile = profiles.find((p) => p.id === deleteProfileId);
    if (profile?.isActive) {
      toast.error("Cannot delete the active profile");
      return;
    }

    try {
      await deleteProfile.mutateAsync({ profileId: deleteProfileId, userId });
      toast.success("Profile deleted");
      setShowDeleteDialog(false);
      setDeleteProfileId(null);
    } catch {
      toast.error("Failed to delete profile");
    }
  };

  const openDuplicateDialog = (profileId: number) => {
    const profile = profiles.find((p) => p.id === profileId);
    setDuplicateProfileId(profileId);
    setDuplicateName(`${profile?.name} (Copy)`);
    setShowDuplicateDialog(true);
  };

  const openDeleteDialog = (profileId: number) => {
    setDeleteProfileId(profileId);
    setShowDeleteDialog(true);
  };

  if (isLoading) {
    return (
      <ProfileSelectorWrapper variant={variant} className={className}>
        <div className="animate-pulse space-y-3">
          <div className="h-4 w-32 rounded bg-surface-muted" />
          <div className="h-10 rounded bg-surface-muted" />
        </div>
      </ProfileSelectorWrapper>
    );
  }

  return (
    <>
      <ProfileSelectorWrapper variant={variant} className={className}>
          <div className="flex items-center justify-between">
            <Label>Settings Profiles</Label>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowImportDialog(true)}
              >
                <Upload className="mr-2 h-4 w-4" />
                Import
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowSaveDialog(true)}
              >
                <Save className="mr-2 h-4 w-4" />
                Save As
              </Button>
            </div>
          </div>

          <div className="space-y-2">
            <Select
              value={activeProfile?.id.toString() || ""}
              onValueChange={(value) => handleLoad(parseInt(value))}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a profile..." />
              </SelectTrigger>
              <SelectContent>
                {profiles.map((profile) => (
                  <SelectItem key={profile.id} value={profile.id.toString()}>
                    <div className="flex items-center gap-2">
                      {profile.isActive && (
                        <Check className="h-4 w-4 text-primary" />
                      )}
                      <span>{profile.name}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {activeProfile && (
              <div className="rounded-lg border border-border bg-surface-muted/30 p-3">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-sm font-medium text-text">
                    {activeProfile.name}
                  </p>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleExport(activeProfile.id)}
                      className="h-8 px-2"
                    >
                      <Download className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openDuplicateDialog(activeProfile.id)}
                      className="h-8 px-2"
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                    {profiles.length > 1 && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openDeleteDialog(activeProfile.id)}
                        className="h-8 px-2 text-loss hover:text-loss"
                        disabled={activeProfile.isActive}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </div>
                {activeProfile.description && (
                  <p className="text-xs text-text-muted">
                    {activeProfile.description}
                  </p>
                )}
                <p className="mt-1 text-xs text-text-muted">
                  Updated: {new Date(activeProfile.updatedAt).toLocaleDateString()}
                </p>
              </div>
            )}
          </div>

          <p className="text-xs text-text-muted">
            Save different configurations for various trading strategies. Profiles
            store all your preferences including risk tolerance, weights, and display
            settings.
          </p>
      </ProfileSelectorWrapper>

      {/* Save Profile Dialog */}
      <Dialog open={showSaveDialog} onOpenChange={setShowSaveDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save Settings Profile</DialogTitle>
            <DialogDescription>
              Create a new profile with your current settings
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="profile-name">Profile Name *</Label>
              <Input
                id="profile-name"
                value={saveName}
                onChange={(e) => setSaveName(e.target.value)}
                placeholder="e.g., Aggressive Growth, Conservative Income"
              />
            </div>
            <div>
              <Label htmlFor="profile-description">Description (optional)</Label>
              <Textarea
                id="profile-description"
                value={saveDescription}
                onChange={(e) => setSaveDescription(e.target.value)}
                placeholder="Brief description of this strategy..."
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSaveDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={createProfile.isPending}>
              {createProfile.isPending ? "Saving..." : "Save Profile"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Import Profile Dialog */}
      <Dialog open={showImportDialog} onOpenChange={setShowImportDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Import Settings Profile</DialogTitle>
            <DialogDescription>
              Paste the exported profile JSON data
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Textarea
              value={importData}
              onChange={(e) => setImportData(e.target.value)}
              placeholder='{"name": "...", "profile_data": {...}}'
              rows={10}
              className="font-mono text-xs"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowImportDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleImport} disabled={importProfile.isPending}>
              {importProfile.isPending ? "Importing..." : "Import Profile"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Duplicate Profile Dialog */}
      <Dialog open={showDuplicateDialog} onOpenChange={setShowDuplicateDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Duplicate Profile</DialogTitle>
            <DialogDescription>
              Create a copy of this profile with a new name
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="duplicate-name">New Profile Name *</Label>
              <Input
                id="duplicate-name"
                value={duplicateName}
                onChange={(e) => setDuplicateName(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowDuplicateDialog(false)}
            >
              Cancel
            </Button>
            <Button onClick={handleDuplicate} disabled={duplicateProfile.isPending}>
              {duplicateProfile.isPending ? "Duplicating..." : "Duplicate"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Profile Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Profile</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this profile? This action cannot be
              undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteProfile.isPending}
            >
              {deleteProfile.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
