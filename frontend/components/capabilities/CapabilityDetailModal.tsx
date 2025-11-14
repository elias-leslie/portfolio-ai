/**
 * CapabilityDetailModal component for viewing detailed capability information
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { StatusBadge } from "./StatusBadge";
import { InsightCard } from "./InsightCard";
import {
  Database,
  Zap,
  Globe,
  AlertCircle,
  MessageSquare,
  Network,
  Loader2,
  Save,
  Hash,
  Clock,
  Calendar,
} from "lucide-react";
import type {
  Capability,
  CapabilityType,
  DbCapability,
  CeleryCapability,
  ApiCapability,
  NoteType,
} from "@/lib/api/capabilities";
import {
  fetchCapabilityDetail,
  reviewInsight,
  createNote,
} from "@/lib/api/capabilities";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";

interface CapabilityDetailModalProps {
  capability: Capability | null;
  isOpen: boolean;
  onClose: () => void;
}

/**
 * Get icon for capability type
 */
function getCapabilityIcon(type: CapabilityType) {
  switch (type) {
    case "db":
      return <Database className="h-5 w-5" />;
    case "celery":
      return <Zap className="h-5 w-5" />;
    case "api":
      return <Globe className="h-5 w-5" />;
  }
}

/**
 * CapabilityDetailModal component
 */
export function CapabilityDetailModal({
  capability,
  isOpen,
  onClose,
}: CapabilityDetailModalProps) {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("overview");
  const [noteType, setNoteType] = useState<NoteType>("observation");
  const [noteText, setNoteText] = useState("");
  const [isSavingNote, setIsSavingNote] = useState(false);

  // Fetch detailed capability data
  const { data: detailData, isLoading } = useQuery({
    queryKey: ["capability-detail", capability?.capability_type, capability?.id],
    queryFn: () => {
      if (!capability) throw new Error("No capability selected");
      return fetchCapabilityDetail(capability.capability_type, capability.id);
    },
    enabled: isOpen && !!capability,
  });

  // Review insight mutation
  const reviewMutation = useMutation({
    mutationFn: ({
      insightId,
      status,
      reason,
    }: {
      insightId: number;
      status: "confirmed" | "dismissed" | "in_progress" | "fixed";
      reason: string;
    }) => reviewInsight(insightId, { status, status_reason: reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["capability-detail", capability?.capability_type, capability?.id],
      });
      queryClient.invalidateQueries({ queryKey: ["capabilities"] });
      queryClient.invalidateQueries({ queryKey: ["insights"] });
      toast.success("Insight updated successfully");
    },
    onError: (error: Error) => {
      toast.error(`Failed to update insight: ${error.message}`);
    },
  });

  // Save note
  const handleSaveNote = async () => {
    if (!noteText.trim() || !capability) return;

    setIsSavingNote(true);
    try {
      await createNote({
        capability_type: capability.capability_type,
        capability_id: capability.id,
        note_type: noteType,
        note: noteText,
      });

      toast.success("Note added successfully");
      setNoteText("");
      setNoteType("observation");

      // Refresh detail data
      queryClient.invalidateQueries({
        queryKey: ["capability-detail", capability.capability_type, capability.id],
      });
    } catch (error) {
      toast.error(`Failed to add note: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setIsSavingNote(false);
    }
  };

  if (!capability) return null;

  const capabilityName =
    capability.capability_type === "db"
      ? (capability as DbCapability).table_name
      : capability.capability_type === "celery"
      ? (capability as CeleryCapability).task_name
      : (capability as ApiCapability).endpoint_path;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="rounded-md bg-surface-muted p-2">
                {getCapabilityIcon(capability.capability_type)}
              </div>
              <div>
                <DialogTitle className="text-xl">{capabilityName}</DialogTitle>
                <DialogDescription className="flex items-center gap-2 mt-1">
                  <StatusBadge type="category" value={capability.category || "unknown"} />
                  <span className="text-xs">
                    {capability.insights_count} insights • {capability.notes_count} notes
                  </span>
                </DialogDescription>
              </div>
            </div>
          </div>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-4">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="insights">
              Insights
              {detailData && detailData.insights.length > 0 && (
                <span className="ml-2 rounded-full bg-accent/20 px-2 py-0.5 text-xs">
                  {detailData.insights.length}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="notes">
              Notes
              {detailData && detailData.notes.length > 0 && (
                <span className="ml-2 rounded-full bg-accent/20 px-2 py-0.5 text-xs">
                  {detailData.notes.length}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="dependencies">Dependencies</TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-4 pt-4">
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <OverviewTab capability={capability} />
            )}
          </TabsContent>

          {/* Insights Tab */}
          <TabsContent value="insights" className="space-y-4 pt-4">
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : detailData && detailData.insights.length > 0 ? (
              <div className="space-y-3">
                {detailData.insights.map((insight) => (
                  <InsightCard
                    key={insight.id}
                    insight={insight}
                    onReview={async (insightId, status, reason) => {
                      await reviewMutation.mutateAsync({ insightId, status, reason });
                    }}
                    isLoading={reviewMutation.isPending}
                  />
                ))}
              </div>
            ) : (
              <div className="rounded-lg border border-border bg-surface p-8 text-center">
                <AlertCircle className="mx-auto h-12 w-12 text-muted-foreground opacity-50" />
                <p className="mt-4 text-sm text-muted-foreground">No insights available</p>
              </div>
            )}
          </TabsContent>

          {/* Notes Tab */}
          <TabsContent value="notes" className="space-y-4 pt-4">
            {/* Add Note Form */}
            <div className="rounded-lg border border-border bg-surface p-4 space-y-3">
              <Label htmlFor="note-type">Add a note</Label>
              <Select value={noteType} onValueChange={(val) => setNoteType(val as NoteType)}>
                <SelectTrigger id="note-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="observation">Observation</SelectItem>
                  <SelectItem value="recommendation">Recommendation</SelectItem>
                  <SelectItem value="question">Question</SelectItem>
                  <SelectItem value="decision">Decision</SelectItem>
                  <SelectItem value="reference">Reference</SelectItem>
                </SelectContent>
              </Select>
              <Textarea
                placeholder="Enter your note..."
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                className="min-h-[100px]"
              />
              <Button onClick={handleSaveNote} disabled={isSavingNote || !noteText.trim()}>
                {isSavingNote ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-2 h-4 w-4" />
                )}
                Save Note
              </Button>
            </div>

            {/* Notes List */}
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : detailData && detailData.notes.length > 0 ? (
              <div className="space-y-3">
                {detailData.notes.map((note) => (
                  <div key={note.id} className="rounded-lg border border-border bg-surface p-4">
                    <div className="mb-2 flex items-center justify-between">
                      <StatusBadge type="category" value={note.note_type} />
                      <span className="text-xs text-muted-foreground">
                        {formatDistanceToNow(new Date(note.created_at), { addSuffix: true })} by{" "}
                        {note.created_by}
                      </span>
                    </div>
                    <p className="text-sm text-text">{note.note}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-lg border border-border bg-surface p-8 text-center">
                <MessageSquare className="mx-auto h-12 w-12 text-muted-foreground opacity-50" />
                <p className="mt-4 text-sm text-muted-foreground">No notes yet</p>
              </div>
            )}
          </TabsContent>

          {/* Dependencies Tab */}
          <TabsContent value="dependencies" className="space-y-4 pt-4">
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <DependenciesTab dependencies={detailData?.dependencies || {}} />
            )}
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Overview Tab Component
 */
function OverviewTab({ capability }: { capability: Capability }) {
  const renderDbOverview = (db: DbCapability) => (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Table Name</p>
          <p className="text-sm font-medium">{db.table_name}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Freshness Status</p>
          <StatusBadge type="freshness" value={db.freshness_status} />
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Row Count</p>
          <p className="text-sm font-medium">
            <Hash className="inline h-3 w-3" /> {db.row_count?.toLocaleString() || "0"}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Age</p>
          <p className="text-sm font-medium">
            <Clock className="inline h-3 w-3" />{" "}
            {db.age_hours !== null ? `${db.age_hours.toFixed(1)} hours` : "—"}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Source</p>
          <p className="text-sm font-medium">{db.source || "—"}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            Expected Refresh (hours)
          </p>
          <p className="text-sm font-medium">{db.expected_refresh_hours}</p>
        </div>
      </div>
      {db.description && (
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">Description</p>
          <p className="text-sm text-text">{db.description}</p>
        </div>
      )}
      {db.columns && db.columns.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground mb-2">
            Columns ({db.columns.length})
          </p>
          <div className="flex flex-wrap gap-2">
            {db.columns.map((col) => (
              <span
                key={col}
                className="rounded-md bg-surface-muted px-2 py-1 text-xs font-mono text-text"
              >
                {col}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  const renderCeleryOverview = (celery: CeleryCapability) => (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Task Name</p>
          <p className="text-sm font-medium font-mono">{celery.task_name}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Schedule Type</p>
          <p className="text-sm font-medium">{celery.schedule_type || "—"}</p>
        </div>
        <div className="col-span-2">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Schedule</p>
          <p className="text-sm font-medium">{celery.schedule_interval || "—"}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Last Run</p>
          <p className="text-sm font-medium">
            <Calendar className="inline h-3 w-3" />{" "}
            {celery.last_run_at
              ? formatDistanceToNow(new Date(celery.last_run_at), { addSuffix: true })
              : "Never"}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Last Status</p>
          {celery.last_run_status ? (
            <StatusBadge
              type="status"
              value={celery.last_run_status === "SUCCESS" ? "confirmed" : "dismissed"}
            />
          ) : (
            <p className="text-sm font-medium">—</p>
          )}
        </div>
      </div>
      {celery.description && (
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">Description</p>
          <p className="text-sm text-text">{celery.description}</p>
        </div>
      )}
    </div>
  );

  const renderApiOverview = (api: ApiCapability) => (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="col-span-2">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Endpoint Path</p>
          <p className="text-sm font-medium font-mono">{api.endpoint_path}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">HTTP Method</p>
          <StatusBadge type="category" value={api.http_method} />
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Response Format</p>
          <p className="text-sm font-medium">{api.response_format || "JSON"}</p>
        </div>
      </div>
      {api.description && (
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">Description</p>
          <p className="text-sm text-text">{api.description}</p>
        </div>
      )}
    </div>
  );

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      {capability.capability_type === "db" && renderDbOverview(capability as DbCapability)}
      {capability.capability_type === "celery" &&
        renderCeleryOverview(capability as CeleryCapability)}
      {capability.capability_type === "api" && renderApiOverview(capability as ApiCapability)}
    </div>
  );
}

/**
 * Dependencies Tab Component
 */
function DependenciesTab({
  dependencies,
}: {
  dependencies: {
    populates_tables?: string[];
    depends_on_tasks?: string[];
    depends_on_tables?: string[];
  };
}) {
  const hasAnyDependencies =
    (dependencies.populates_tables?.length || 0) > 0 ||
    (dependencies.depends_on_tasks?.length || 0) > 0 ||
    (dependencies.depends_on_tables?.length || 0) > 0;

  if (!hasAnyDependencies) {
    return (
      <div className="rounded-lg border border-border bg-surface p-8 text-center">
        <Network className="mx-auto h-12 w-12 text-muted-foreground opacity-50" />
        <p className="mt-4 text-sm text-muted-foreground">No dependencies tracked</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {dependencies.populates_tables && dependencies.populates_tables.length > 0 && (
        <div className="rounded-lg border border-border bg-surface p-4">
          <p className="mb-3 text-sm font-medium text-text">Populates Tables</p>
          <div className="flex flex-wrap gap-2">
            {dependencies.populates_tables.map((table) => (
              <span
                key={table}
                className="rounded-md bg-surface-muted px-3 py-1 text-xs font-mono text-text"
              >
                <Database className="mr-1 inline h-3 w-3" />
                {table}
              </span>
            ))}
          </div>
        </div>
      )}

      {dependencies.depends_on_tasks && dependencies.depends_on_tasks.length > 0 && (
        <div className="rounded-lg border border-border bg-surface p-4">
          <p className="mb-3 text-sm font-medium text-text">Depends On Tasks</p>
          <div className="flex flex-wrap gap-2">
            {dependencies.depends_on_tasks.map((task) => (
              <span
                key={task}
                className="rounded-md bg-surface-muted px-3 py-1 text-xs font-mono text-text"
              >
                <Zap className="mr-1 inline h-3 w-3" />
                {task}
              </span>
            ))}
          </div>
        </div>
      )}

      {dependencies.depends_on_tables && dependencies.depends_on_tables.length > 0 && (
        <div className="rounded-lg border border-border bg-surface p-4">
          <p className="mb-3 text-sm font-medium text-text">Depends On Tables</p>
          <div className="flex flex-wrap gap-2">
            {dependencies.depends_on_tables.map((table) => (
              <span
                key={table}
                className="rounded-md bg-surface-muted px-3 py-1 text-xs font-mono text-text"
              >
                <Database className="mr-1 inline h-3 w-3" />
                {table}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
