"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Save, Edit2, X } from "lucide-react";
import { useUpdateWatchlistItem } from "@/lib/hooks/useWatchlist";
import { toast } from "sonner";
import type { WatchlistItem } from "@/lib/api/watchlist";

interface ExpandedRowNotesProps {
    item: WatchlistItem;
}

/**
 * Notes editing component for watchlist expanded row
 *
 * Allows users to add/edit personal notes for watchlist items:
 * - Edit mode with character counter (200 char limit)
 * - Save/cancel actions
 * - Optimistic updates with error handling
 *
 * Extracted from ExpandedRow.tsx to reduce file size.
 */
export function ExpandedRowNotes({ item }: ExpandedRowNotesProps) {
    const [isEditingNote, setIsEditingNote] = useState(false);
    const [noteValue, setNoteValue] = useState(item.note || "");
    const updateMutation = useUpdateWatchlistItem();

    const handleSaveNote = () => {
        updateMutation.mutate(
            {
                itemId: item.id,
                data: { note: noteValue.trim() || undefined },
            },
            {
                onSuccess: () => {
                    toast.success("Note updated");
                    setIsEditingNote(false);
                },
                onError: (error) => {
                    toast.error(`Failed to update note: ${error.message}`);
                },
            },
        );
    };

    const handleCancelEdit = () => {
        setNoteValue(item.note || "");
        setIsEditingNote(false);
    };

    return (
        <Card className="border-border">
            <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center justify-between">
                    Notes
                    {!isEditingNote && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setIsEditingNote(true)}
                            className="h-8"
                        >
                            <Edit2 className="mr-1 h-3 w-3" />
                            Edit
                        </Button>
                    )}
                </CardTitle>
            </CardHeader>
            <CardContent>
                {isEditingNote ? (
                    <div className="space-y-3">
                        <Input
                            value={noteValue}
                            onChange={(e) => setNoteValue(e.target.value)}
                            placeholder="Add a note about this symbol..."
                            maxLength={200}
                            className="w-full"
                            autoFocus
                        />
                        <div className="flex items-center justify-between">
                            <p className="text-xs text-text-muted">
                                {noteValue.length}/200 characters
                            </p>
                            <div className="flex gap-2">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={handleCancelEdit}
                                    disabled={updateMutation.isPending}
                                >
                                    <X className="mr-1 h-3 w-3" />
                                    Cancel
                                </Button>
                                <Button
                                    size="sm"
                                    onClick={handleSaveNote}
                                    disabled={updateMutation.isPending}
                                >
                                    <Save className="mr-1 h-3 w-3" />
                                    Save
                                </Button>
                            </div>
                        </div>
                    </div>
                ) : (
                    <p className="text-sm text-text-muted">
                        {item.note || "No notes yet. Click Edit to add one."}
                    </p>
                )}
            </CardContent>
        </Card>
    );
}
