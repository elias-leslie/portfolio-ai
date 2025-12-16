"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Image as ImageIcon,
  Terminal,
  Network,
  FileJson,
  Loader2,
  ExternalLink,
} from "lucide-react";

interface Evidence {
  metadata: {
    url: string;
    featureId: string;
    criterionId: string;
    version: number;
    capturedAt: string;
    pageTitle: string;
    viewport: { width: number; height: number };
    captureTimeMs: number;
  };
  console: {
    errorCount: number;
    warningCount: number;
    errors: Array<{ text: string; source: string | null }>;
    warnings: Array<{ text: string; source: string | null }>;
  };
  network: {
    totalRequests: number;
    failedRequests: number;
    failures: Array<{ url: string; status: number | string; error?: string }>;
    slowRequests: Array<{ url: string; durationMs: number }>;
  };
  pageState: {
    hasContent: boolean;
    visibleTextSample: string;
    keyElements: {
      tables: number;
      charts: number;
      buttons: number;
      errorMessages: number;
      loadingSpinners: number;
      emptyStates: number;
    };
  };
  performance: {
    pageLoadMs: number | null;
    domContentLoadedMs: number | null;
    largestContentfulPaintMs: number | null;
  };
}

interface Artifact {
  id: number;
  artifactId: string;
  featureId: string;
  criterionId: string;
  version: number;
  isCurrent: boolean;
  capturedAt: string;
  expiresAt: string;
  qualityStatus: string;
  confidence: number | null;
  userApproved: boolean | null;
  userNotes: string | null;
  fileSizeBytes: number;
}

interface ArtifactResponse {
  artifact: Artifact;
  versions: Artifact[];
  evidence: Evidence | null;
  screenshotUrl: string;
  evidenceUrl: string;
}

interface EvidenceViewerModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  featureId: string;
  criterionId: string;
  criterionText?: string;
  verificationUrl?: string; // URL parsed from criterion verification text
}

export function EvidenceViewerModal({
  open,
  onOpenChange,
  featureId,
  criterionId,
  criterionText,
  verificationUrl,
}: EvidenceViewerModalProps) {
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [userNotes, setUserNotes] = useState("");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState("screenshot");
  const queryClient = useQueryClient();

  // Fetch artifact data
  // IMPORTANT: Always refetch on mount to avoid stale cached 404 errors
  const { data, isLoading, error, refetch } = useQuery<ArtifactResponse>({
    queryKey: ["artifact", featureId, criterionId, selectedVersion],
    queryFn: async () => {
      const params = new URLSearchParams({ includeEvidence: "true" });
      if (selectedVersion) params.set("version", String(selectedVersion));
      const response = await fetch(
        `/api/artifacts/${featureId}/${criterionId}?${params}`
      );
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error("No evidence captured yet");
        }
        throw new Error("Failed to fetch artifact");
      }
      return response.json();
    },
    enabled: open && !!featureId && !!criterionId,
    staleTime: 0, // Always consider data stale
    refetchOnMount: "always", // Always refetch when modal opens
    retry: 1, // Only retry once on failure
  });

  // Set initial version from data
  useEffect(() => {
    if (data?.artifact && !selectedVersion) {
      setSelectedVersion(data.artifact.version);
    }
  }, [data, selectedVersion]);

  // Reset state when modal closes to ensure fresh fetch on reopen
  useEffect(() => {
    if (!open) {
      setSelectedVersion(null);
      setUserNotes("");
      setActiveTab("screenshot");
    }
  }, [open]);

  // Submit user review mutation
  const reviewMutation = useMutation({
    mutationFn: async ({
      approved,
      notes,
    }: {
      approved: boolean | null;
      notes: string;
    }) => {
      const response = await fetch(
        `/api/artifacts/${data?.artifact.artifactId}/review`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ approved, notes }),
        }
      );
      if (!response.ok) throw new Error("Failed to submit review");
      return response.json();
    },
    onSuccess: () => {
      toast.success("Review submitted");
      queryClient.invalidateQueries({
        queryKey: ["artifact", featureId, criterionId],
      });
    },
    onError: () => {
      toast.error("Failed to submit review");
    },
  });

  // Navigate versions
  const handlePrevVersion = () => {
    if (data?.versions && selectedVersion) {
      const currentIdx = data.versions.findIndex(
        (v) => v.version === selectedVersion
      );
      if (currentIdx < data.versions.length - 1) {
        setSelectedVersion(data.versions[currentIdx + 1].version);
      }
    }
  };

  const handleNextVersion = () => {
    if (data?.versions && selectedVersion) {
      const currentIdx = data.versions.findIndex(
        (v) => v.version === selectedVersion
      );
      if (currentIdx > 0) {
        setSelectedVersion(data.versions[currentIdx - 1].version);
      }
    }
  };

  // Refresh evidence
  const handleRefresh = async () => {
    // Use existing evidence URL, or fallback to parsed verification URL
    const captureUrl = data?.evidence?.metadata.url || verificationUrl;
    if (!captureUrl) {
      toast.error("No URL available for capture");
      return;
    }

    setIsRefreshing(true);
    try {
      const response = await fetch("/api/artifacts/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          featureId: featureId,
          criterionId: criterionId,
          url: captureUrl,
        }),
      });
      if (!response.ok) throw new Error("Refresh failed");
      const result = await response.json();
      if (result.success) {
        toast.success(`Evidence refreshed (v${result.version})`);
        setSelectedVersion(result.version);
        // Invalidate and refetch to show new evidence immediately
        await queryClient.invalidateQueries({
          queryKey: ["artifact", featureId, criterionId],
        });
        // Force refetch the current query
        refetch();
      } else {
        toast.error(`Refresh failed: ${result.error}`);
      }
    } catch {
      toast.error("Failed to refresh evidence");
    } finally {
      setIsRefreshing(false);
    }
  };

  const evidence = data?.evidence;
  const artifact = data?.artifact;
  const versions = data?.versions || [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="!max-w-[95vw] w-fit min-w-[50vw] h-[95vh] flex flex-col p-0 gap-0 overflow-hidden">
        <DialogHeader className="p-4 border-b shrink-0">
          <DialogTitle className="flex items-center gap-2">
            Evidence: {featureId} / {criterionId}
            {artifact && (
              <Badge
                variant="outline"
                className={
                  artifact.qualityStatus === "passed"
                    ? "bg-green-500/20 text-green-400"
                    : artifact.qualityStatus === "failed"
                      ? "bg-red-500/20 text-red-400"
                      : "bg-yellow-500/20 text-yellow-400"
                }
              >
                {artifact.qualityStatus}
              </Badge>
            )}
          </DialogTitle>
          {criterionText && (
            <DialogDescription className="text-sm">
              {criterionText}
            </DialogDescription>
          )}
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-12 flex-1">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-12 gap-4 flex-1">
            <AlertTriangle className="h-12 w-12 text-yellow-500" />
            <p className="text-sm text-muted-foreground">
              {error instanceof Error ? error.message : "Failed to load evidence"}
            </p>
            <Button onClick={handleRefresh} disabled={isRefreshing}>
              {isRefreshing ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4 mr-2" />
              )}
              Capture Evidence
            </Button>
          </div>
        ) : evidence ? (
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
            {/* Version navigation and actions */}
            <div className="flex items-center justify-between p-2 border-b border-border bg-muted/20 shrink-0">
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handlePrevVersion}
                  disabled={
                    !versions.length ||
                    selectedVersion === versions[versions.length - 1]?.version
                  }
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="text-sm font-mono">
                  v{selectedVersion} / {versions.length}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleNextVersion}
                  disabled={
                    !versions.length || selectedVersion === versions[0]?.version
                  }
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
                <span className="text-xs text-muted-foreground ml-2">
                  {artifact?.capturedAt &&
                    new Date(artifact.capturedAt).toLocaleString()}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRefresh}
                  disabled={isRefreshing}
                >
                  {isRefreshing ? (
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                  ) : (
                    <RefreshCw className="h-4 w-4 mr-1" />
                  )}
                  Refresh
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  asChild
                >
                  <a
                    href={evidence.metadata.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <ExternalLink className="h-4 w-4 mr-1" />
                    Open Page
                  </a>
                </Button>
              </div>
            </div>

            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0 overflow-hidden">
              <div className="px-4 pt-2 border-b shrink-0">
                <TabsList className="w-full justify-start bg-transparent p-0 h-auto gap-4">
                  <TabsTrigger
                    value="screenshot"
                    className="gap-1 data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none px-2 py-2"
                  >
                    <ImageIcon className="h-4 w-4" />
                    Screenshot
                  </TabsTrigger>
                  <TabsTrigger
                    value="console"
                    className="gap-1 data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none px-2 py-2"
                  >
                    <Terminal className="h-4 w-4" />
                    Console
                    {evidence.console.errorCount > 0 && (
                      <Badge variant="destructive" className="ml-1 h-5 px-1">
                        {evidence.console.errorCount}
                      </Badge>
                    )}
                  </TabsTrigger>
                  <TabsTrigger
                    value="network"
                    className="gap-1 data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none px-2 py-2"
                  >
                    <Network className="h-4 w-4" />
                    Network
                    {evidence.network.failedRequests > 0 && (
                      <Badge variant="destructive" className="ml-1 h-5 px-1">
                        {evidence.network.failedRequests}
                      </Badge>
                    )}
                  </TabsTrigger>
                  <TabsTrigger
                    value="page"
                    className="gap-1 data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none px-2 py-2"
                  >
                    <FileJson className="h-4 w-4" />
                    Page State
                  </TabsTrigger>
                </TabsList>
              </div>

              <div className="flex-1 overflow-hidden relative bg-muted/10">
                <TabsContent value="screenshot" className="m-0 absolute inset-0 overflow-auto p-4">
                  <img
                    src={data?.screenshotUrl}
                    alt="Page screenshot"
                    className="border border-border shadow-sm"
                  />
                </TabsContent>

                <TabsContent value="console" className="m-0 absolute inset-0 overflow-auto p-4">
                  <div className="space-y-4 max-w-4xl mx-auto">
                    <div className="flex gap-4 text-sm font-medium">
                      <span className="text-red-400 flex items-center gap-1">
                        <XCircle className="h-4 w-4" />
                        {evidence.console.errorCount} errors
                      </span>
                      <span className="text-yellow-400 flex items-center gap-1">
                        <AlertTriangle className="h-4 w-4" />
                        {evidence.console.warningCount} warnings
                      </span>
                    </div>

                    {evidence.console.errors.length > 0 && (
                      <div className="space-y-2">
                        <h4 className="text-sm font-medium border-b pb-1">Errors</h4>
                        {evidence.console.errors.map((err, i) => (
                          <div
                            key={i}
                            className="rounded bg-red-500/5 border border-red-500/20 p-3"
                          >
                            <p className="text-sm text-red-400 font-mono break-all whitespace-pre-wrap">
                              {err.text}
                            </p>
                            {err.source && (
                              <p className="text-xs text-muted-foreground mt-1 border-t border-red-500/10 pt-1">
                                {err.source}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    {evidence.console.warnings.length > 0 && (
                      <div className="space-y-2">
                        <h4 className="text-sm font-medium border-b pb-1">Warnings</h4>
                        {evidence.console.warnings.map((warn, i) => (
                          <div
                            key={i}
                            className="rounded bg-yellow-500/5 border border-yellow-500/20 p-3"
                          >
                            <p className="text-sm text-yellow-400 font-mono break-all whitespace-pre-wrap">
                              {warn.text}
                            </p>
                            {warn.source && (
                              <p className="text-xs text-muted-foreground mt-1 border-t border-yellow-500/10 pt-1">
                                {warn.source}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    {evidence.console.errors.length === 0 &&
                      evidence.console.warnings.length === 0 && (
                        <div className="text-center py-12 text-muted-foreground">
                          <CheckCircle2 className="h-12 w-12 mx-auto mb-2 text-green-500/20" />
                          <p>No console errors or warnings captured.</p>
                        </div>
                      )}
                  </div>
                </TabsContent>

                <TabsContent value="network" className="m-0 absolute inset-0 overflow-auto p-4">
                  <div className="space-y-6 max-w-4xl mx-auto">
                    <div className="grid grid-cols-3 gap-4">
                      <div className="p-4 rounded border border-border bg-background">
                        <div className="text-2xl font-bold">{evidence.network.totalRequests}</div>
                        <div className="text-sm text-muted-foreground">Total Requests</div>
                      </div>
                      <div className="p-4 rounded border border-border bg-background">
                        <div className="text-2xl font-bold text-red-400">{evidence.network.failedRequests}</div>
                        <div className="text-sm text-muted-foreground">Failed</div>
                      </div>
                      <div className="p-4 rounded border border-border bg-background">
                        <div className="text-2xl font-bold text-yellow-400">{evidence.network.slowRequests.length}</div>
                        <div className="text-sm text-muted-foreground">Slow ({">"}3s)</div>
                      </div>
                    </div>

                    {evidence.network.failures.length > 0 && (
                      <div className="space-y-2">
                        <h4 className="text-sm font-medium border-b pb-1">Failed Requests</h4>
                        {evidence.network.failures.map((fail, i) => (
                          <div
                            key={i}
                            className="rounded bg-red-500/5 border border-red-500/20 p-3"
                          >
                            <div className="flex items-start gap-2">
                              <Badge variant="destructive" className="mt-0.5">{fail.status}</Badge>
                              <p className="text-sm font-mono break-all flex-1">
                                {fail.url}
                              </p>
                            </div>
                            {fail.error && (
                              <p className="text-xs text-red-300 mt-2 pl-12">
                                Error: {fail.error}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    {evidence.network.slowRequests.length > 0 && (
                      <div className="space-y-2">
                        <h4 className="text-sm font-medium border-b pb-1">Slow Requests</h4>
                        {evidence.network.slowRequests.map((req, i) => (
                          <div
                            key={i}
                            className="rounded bg-yellow-500/5 border border-yellow-500/20 p-3 flex justify-between gap-4"
                          >
                            <p className="text-sm font-mono break-all flex-1">
                              {req.url}
                            </p>
                            <span className="text-sm text-yellow-400 font-mono whitespace-nowrap">
                              {req.durationMs}ms
                            </span>
                          </div>
                        ))}
                      </div>
                    )}

                    {evidence.network.failures.length === 0 &&
                      evidence.network.slowRequests.length === 0 && (
                        <div className="text-center py-12 text-muted-foreground">
                          <CheckCircle2 className="h-12 w-12 mx-auto mb-2 text-green-500/20" />
                          <p>All network requests completed successfully.</p>
                        </div>
                      )}
                  </div>
                </TabsContent>

                <TabsContent value="page" className="m-0 absolute inset-0 overflow-auto p-4">
                  <div className="space-y-6 max-w-4xl mx-auto">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-4 rounded border border-border bg-background">
                        <h4 className="text-sm font-semibold mb-1">Page Title</h4>
                        <p className="text-sm">{evidence.metadata.pageTitle}</p>
                      </div>
                      <div className="p-4 rounded border border-border bg-background">
                        <h4 className="text-sm font-semibold mb-1">Viewport</h4>
                        <p className="text-sm font-mono">{evidence.metadata.viewport.width} x {evidence.metadata.viewport.height}</p>
                      </div>
                    </div>

                    <div>
                      <h4 className="text-sm font-medium mb-3">Key Elements Found</h4>
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                        {Object.entries(evidence.pageState.keyElements).map(
                          ([key, value]) => (
                            <div
                              key={key}
                              className={`p-3 rounded border flex justify-between items-center ${key === "errorMessages" && value > 0
                                ? "border-red-500/30 bg-red-500/5"
                                : "border-border bg-background"
                                }`}
                            >
                              <span className="text-sm text-muted-foreground capitalize">
                                {key.replace(/([A-Z])/g, " $1").trim()}
                              </span>
                              <span
                                className={`font-mono font-medium ${key === "errorMessages" && value > 0
                                  ? "text-red-400"
                                  : ""
                                  }`}
                              >
                                {value}
                              </span>
                            </div>
                          )
                        )}
                      </div>
                    </div>

                    <div>
                      <h4 className="text-sm font-medium mb-3">Performance Metrics</h4>
                      <div className="grid grid-cols-3 gap-4">
                        <div className="p-3 rounded border border-border bg-background">
                          <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Page Load</div>
                          <div className="text-xl font-mono">{evidence.performance.pageLoadMs ?? "N/A"}<span className="text-sm text-muted-foreground ml-1">ms</span></div>
                        </div>
                        <div className="p-3 rounded border border-border bg-background">
                          <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">DOM Ready</div>
                          <div className="text-xl font-mono">{evidence.performance.domContentLoadedMs ?? "N/A"}<span className="text-sm text-muted-foreground ml-1">ms</span></div>
                        </div>
                        <div className="p-3 rounded border border-border bg-background">
                          <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">LCP</div>
                          <div className="text-xl font-mono">{evidence.performance.largestContentfulPaintMs ?? "N/A"}<span className="text-sm text-muted-foreground ml-1">ms</span></div>
                        </div>
                      </div>
                    </div>

                    <div>
                      <h4 className="text-sm font-medium mb-2">Visible Text Sample</h4>
                      <div className="p-4 rounded border border-border bg-muted/30 text-sm font-mono text-muted-foreground">
                        {evidence.pageState.visibleTextSample || "No text content"}
                      </div>
                    </div>
                  </div>
                </TabsContent>
              </div>
            </Tabs>

            {/* User review section - Fixed at bottom */}
            <div className="border-t border-border p-4 bg-background shrink-0">
              <div className="max-w-4xl mx-auto space-y-3">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Your Review:</span>
                  {artifact?.userApproved === true && (
                    <Badge className="bg-green-500/20 text-green-400 hover:bg-green-500/30">
                      Approved
                    </Badge>
                  )}
                  {artifact?.userApproved === false && (
                    <Badge className="bg-red-500/20 text-red-400 hover:bg-red-500/30">Rejected</Badge>
                  )}
                </div>
                <div className="flex gap-4">
                  <Textarea
                    placeholder="Add notes about this evidence..."
                    value={userNotes}
                    onChange={(e) => setUserNotes(e.target.value)}
                    rows={2}
                    className="flex-1 resize-none"
                  />
                  <div className="flex flex-col gap-2 shrink-0 w-32">
                    <Button
                      variant="outline"
                      className="w-full flex-1 border-green-500/50 text-green-400 hover:bg-green-500/10 hover:text-green-300"
                      onClick={() =>
                        reviewMutation.mutate({ approved: true, notes: userNotes })
                      }
                      disabled={reviewMutation.isPending}
                    >
                      <CheckCircle2 className="h-4 w-4 mr-2" />
                      Approve
                    </Button>
                    <Button
                      variant="outline"
                      className="w-full flex-1 border-red-500/50 text-red-400 hover:bg-red-500/10 hover:text-red-300"
                      onClick={() =>
                        reviewMutation.mutate({ approved: false, notes: userNotes })
                      }
                      disabled={reviewMutation.isPending}
                    >
                      <XCircle className="h-4 w-4 mr-2" />
                      Reject
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
