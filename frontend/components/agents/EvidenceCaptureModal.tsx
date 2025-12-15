"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Camera,
  Loader2,
  Zap,
  FolderOpen,
  Search,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Link2,
  CheckCircle2,
  Crosshair,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface AcceptanceCriterion {
  id: string;
  criterion: string;
  verification?: string;
  type: string;
  passed?: boolean | null;
}

interface Feature {
  feature_id: string;
  name: string;
  category: string;
  acceptance_criteria: AcceptanceCriterion[];
}

interface EvidenceCaptureResult {
  success: boolean;
  version: number;
  feature_id: string;
  criterion_id: string;
  error?: string;
  evidence?: {
    console: { errorCount: number; warningCount: number };
    network: { failedRequests: number };
    metadata: { url: string; capturedAt: string };
  };
}

interface EvidenceCaptureModalProps {
  open: boolean;
  onClose: () => void;
  pageUrl: string;
  onCaptured: (result: EvidenceCaptureResult) => void;
}

type SortField = "feature_id" | "name" | "category" | "ui_count" | "url_match";
type SortDirection = "asc" | "desc";

// Extract path from URL for matching
function extractPath(url: string): string {
  try {
    const parsed = new URL(url);
    return parsed.pathname;
  } catch {
    // If it's already a path or invalid URL
    return url.startsWith("/") ? url : `/${url}`;
  }
}

// Check if a feature/criterion matches the current URL path
function checkUrlMatch(
  feature: Feature,
  currentPath: string
): { matches: boolean; matchingCriteria: string[] } {
  const matchingCriteria: string[] = [];
  const pathLower = currentPath.toLowerCase();

  for (const criterion of feature.acceptance_criteria) {
    if (criterion.type !== "ui") continue;

    // Check verification field for URL/path
    const verification = criterion.verification?.toLowerCase() || "";
    const criterionText = criterion.criterion.toLowerCase();

    // Match patterns: "screenshot /watchlist", "/watchlist", "http://...//watchlist"
    if (
      verification.includes(pathLower) ||
      criterionText.includes(pathLower) ||
      // Also check if path segments match (e.g., "watchlist" in "/watchlist/details")
      pathLower.split("/").some(
        (segment) =>
          segment && (verification.includes(segment) || criterionText.includes(segment))
      )
    ) {
      matchingCriteria.push(criterion.id);
    }
  }

  return { matches: matchingCriteria.length > 0, matchingCriteria };
}

export function EvidenceCaptureModal({
  open,
  onClose,
  pageUrl,
  onCaptured,
}: EvidenceCaptureModalProps) {
  const [mode, setMode] = useState<"viewport" | "quick" | "existing">("viewport");
  const [selectedFeature, setSelectedFeature] = useState<string>("");
  const [selectedCriterion, setSelectedCriterion] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [urlMatchOnly, setUrlMatchOnly] = useState(false);
  const [sortField, setSortField] = useState<SortField>("url_match");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [isCapturingViewport, setIsCapturingViewport] = useState(false);

  const currentPath = extractPath(pageUrl);

  // Viewport capture function - captures exactly what user sees
  const captureViewport = useCallback(async () => {
    setIsCapturingViewport(true);
    try {
      // Hide the modal temporarily to capture clean screenshot
      const modalElement = document.querySelector('[role="dialog"]');
      if (modalElement) {
        (modalElement as HTMLElement).style.visibility = "hidden";
      }

      // Small delay to ensure modal is hidden
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Dynamically import dom-to-image-more (client-side only)
      const domtoimage = (await import("dom-to-image-more")).default;

      // Capture the document body using dom-to-image-more
      const dataUrl = await domtoimage.toPng(document.body, {
        width: window.innerWidth,
        height: window.innerHeight,
        style: {
          transform: `translate(-${window.scrollX}px, -${window.scrollY}px)`,
        },
        filter: (node: Node) => {
          // Skip noscript and dialog elements
          if (node instanceof Element) {
            if (node.tagName === "NOSCRIPT") return false;
            if (node.getAttribute("role") === "dialog") return false;
          }
          return true;
        },
      });

      // Restore modal visibility
      if (modalElement) {
        (modalElement as HTMLElement).style.visibility = "visible";
      }

      // Convert data URL to base64
      const base64 = dataUrl.split(",")[1];

      // Generate quick debug feature ID
      const timestamp = new Date()
        .toISOString()
        .replace(/[-:T]/g, "")
        .slice(0, 12);
      const featureId = `DBG-${timestamp.slice(4, 8)}-${timestamp.slice(8, 14)}`;
      const criterionId = "viewport";

      // Send to backend
      const response = await fetch("/api/artifacts/viewport-capture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          feature_id: featureId,
          criterion_id: criterionId,
          screenshot_base64: base64,
          url: pageUrl,
          viewport_width: window.innerWidth,
          viewport_height: window.innerHeight,
          scroll_x: window.scrollX,
          scroll_y: window.scrollY,
          page_title: document.title,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to upload screenshot");
      }

      const result = await response.json();
      toast.success(`Viewport captured (v${result.version}) - exactly what you see!`);
      onCaptured(result);
      onClose();
    } catch (error) {
      console.error("Viewport capture failed:", error);
      toast.error("Failed to capture viewport");
      // Restore modal visibility on error
      const modalElement = document.querySelector('[role="dialog"]');
      if (modalElement) {
        (modalElement as HTMLElement).style.visibility = "visible";
      }
    } finally {
      setIsCapturingViewport(false);
    }
  }, [pageUrl, onCaptured, onClose]);

  // Fetch existing features
  const { data: featuresData, isLoading: loadingFeatures } = useQuery<{
    features: Feature[];
  }>({
    queryKey: ["features-for-evidence"],
    queryFn: async () => {
      const response = await fetch("/api/capabilities/features/?limit=200");
      if (!response.ok) throw new Error("Failed to fetch features");
      return response.json();
    },
    enabled: open && mode === "existing",
  });

  // Process features with URL matching and filtering
  const processedFeatures = useMemo(() => {
    if (!featuresData?.features) return [];

    return featuresData.features
      .map((feature) => {
        const uiCriteria = feature.acceptance_criteria.filter((c) => c.type === "ui");
        const urlMatchInfo = checkUrlMatch(feature, currentPath);
        return {
          ...feature,
          uiCriteria,
          uiCount: uiCriteria.length,
          urlMatch: urlMatchInfo.matches,
          matchingCriteriaIds: urlMatchInfo.matchingCriteria,
        };
      })
      .filter((f) => f.uiCount > 0); // Only show features with UI criteria
  }, [featuresData, currentPath]);

  // Filter and sort features
  const filteredFeatures = useMemo(() => {
    let result = processedFeatures;

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(
        (f) =>
          f.feature_id.toLowerCase().includes(query) ||
          f.name.toLowerCase().includes(query) ||
          f.category.toLowerCase().includes(query) ||
          f.uiCriteria.some((c) => c.criterion.toLowerCase().includes(query))
      );
    }

    // URL match filter
    if (urlMatchOnly) {
      result = result.filter((f) => f.urlMatch);
    }

    // Sort
    result.sort((a, b) => {
      let comparison = 0;
      switch (sortField) {
        case "feature_id":
          comparison = a.feature_id.localeCompare(b.feature_id);
          break;
        case "name":
          comparison = a.name.localeCompare(b.name);
          break;
        case "category":
          comparison = a.category.localeCompare(b.category);
          break;
        case "ui_count":
          comparison = a.uiCount - b.uiCount;
          break;
        case "url_match":
          // URL matches first, then by feature ID
          comparison = (b.urlMatch ? 1 : 0) - (a.urlMatch ? 1 : 0);
          if (comparison === 0) {
            comparison = a.feature_id.localeCompare(b.feature_id);
          }
          break;
      }
      return sortDirection === "asc" ? comparison : -comparison;
    });

    return result;
  }, [processedFeatures, searchQuery, urlMatchOnly, sortField, sortDirection]);

  // Get selected feature data
  const selectedFeatureData = processedFeatures.find(
    (f) => f.feature_id === selectedFeature
  );

  // Reset state when modal opens/closes
  useEffect(() => {
    if (!open) {
      setMode("quick");
      setSelectedFeature("");
      setSelectedCriterion("");
      setSearchQuery("");
      setUrlMatchOnly(false);
    }
  }, [open]);

  // Auto-select first matching criterion when feature is selected
  useEffect(() => {
    if (selectedFeatureData && !selectedCriterion) {
      // Prefer matching criteria, otherwise first UI criterion
      if (selectedFeatureData.matchingCriteriaIds.length > 0) {
        setSelectedCriterion(selectedFeatureData.matchingCriteriaIds[0]);
      } else if (selectedFeatureData.uiCriteria.length > 0) {
        setSelectedCriterion(selectedFeatureData.uiCriteria[0].id);
      }
    }
  }, [selectedFeatureData, selectedCriterion]);

  // Quick feature mutation
  const quickFeatureMutation = useMutation({
    mutationFn: async () => {
      const response = await fetch("/api/capabilities/features/quick", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: pageUrl }),
      });
      if (!response.ok) throw new Error("Failed to create quick feature");
      return response.json();
    },
  });

  // Evidence capture mutation
  const captureMutation = useMutation({
    mutationFn: async ({
      featureId,
      criterionId,
    }: {
      featureId: string;
      criterionId: string;
    }) => {
      const response = await fetch("/api/artifacts/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          feature_id: featureId,
          criterion_id: criterionId,
          url: pageUrl,
        }),
      });
      if (!response.ok) throw new Error("Evidence capture failed");
      const result = await response.json();
      return { ...result, feature_id: featureId, criterion_id: criterionId };
    },
    onSuccess: (result) => {
      if (result.success) {
        toast.success(`Evidence captured (v${result.version})`);
        onCaptured(result);
        onClose();
      } else {
        toast.error(`Capture failed: ${result.error}`);
      }
    },
    onError: () => {
      toast.error("Failed to capture evidence");
    },
  });

  // Handle capture
  const handleCapture = async () => {
    if (mode === "viewport") {
      // Use client-side html2canvas capture
      await captureViewport();
    } else if (mode === "quick") {
      try {
        const quickResult = await quickFeatureMutation.mutateAsync();
        await captureMutation.mutateAsync({
          featureId: quickResult.feature_id,
          criterionId: quickResult.criterion_id,
        });
      } catch {
        // Errors handled by mutation callbacks
      }
    } else {
      if (!selectedFeature || !selectedCriterion) {
        toast.error("Please select a feature and criterion");
        return;
      }
      captureMutation.mutate({
        featureId: selectedFeature,
        criterionId: selectedCriterion,
      });
    }
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDirection(field === "url_match" ? "desc" : "asc");
    }
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <ArrowUpDown className="h-3 w-3 opacity-50" />;
    return sortDirection === "asc" ? (
      <ArrowUp className="h-3 w-3" />
    ) : (
      <ArrowDown className="h-3 w-3" />
    );
  };

  const isCapturing = isCapturingViewport || quickFeatureMutation.isPending || captureMutation.isPending;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className={cn(
        "sm:max-w-md transition-all duration-200",
        mode === "existing" && "sm:max-w-2xl"
      )}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Camera className="h-5 w-5" />
            Capture Evidence
          </DialogTitle>
          <DialogDescription>
            Capture screenshot and page state for:{" "}
            <code className="text-xs bg-muted px-1 rounded">{currentPath}</code>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Mode selector */}
          <div className="flex gap-2">
            <Button
              variant={mode === "viewport" ? "default" : "outline"}
              size="sm"
              onClick={() => setMode("viewport")}
              className="flex-1"
            >
              <Crosshair className="h-4 w-4 mr-2" />
              Viewport
            </Button>
            <Button
              variant={mode === "quick" ? "default" : "outline"}
              size="sm"
              onClick={() => setMode("quick")}
              className="flex-1"
            >
              <Zap className="h-4 w-4 mr-2" />
              Quick
            </Button>
            <Button
              variant={mode === "existing" ? "default" : "outline"}
              size="sm"
              onClick={() => setMode("existing")}
              className="flex-1"
            >
              <FolderOpen className="h-4 w-4 mr-2" />
              Feature
            </Button>
          </div>

          {mode === "viewport" ? (
            <div className="rounded-lg border border-primary/30 bg-primary/5 p-4 text-sm space-y-2">
              <p className="font-medium text-primary">
                Captures exactly what you see right now
              </p>
              <ul className="text-muted-foreground text-xs space-y-1">
                <li>• Your current scroll position</li>
                <li>• Expanded sections & accordions</li>
                <li>• Tab selections & form values</li>
                <li>• Modal states (except this one)</li>
              </ul>
              <p className="text-xs text-muted-foreground mt-2">
                No console/network data - just the visual state.
              </p>
            </div>
          ) : mode === "quick" ? (
            <div className="rounded-lg border border-border bg-muted/30 p-4 text-sm text-muted-foreground">
              <p>
                Creates a debug feature (
                <code className="text-xs bg-muted px-1 rounded">DBG-*</code>
                ) and captures evidence immediately.
              </p>
              <p className="mt-2">
                Debug features appear in the Features tab for review.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {/* Search and filter controls */}
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search features..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9 h-9"
                  />
                </div>
                <div className="flex items-center gap-2 px-3 border rounded-md bg-muted/30">
                  <Checkbox
                    id="url-match"
                    checked={urlMatchOnly}
                    onCheckedChange={(c) => setUrlMatchOnly(c === true)}
                  />
                  <Label htmlFor="url-match" className="text-xs cursor-pointer whitespace-nowrap">
                    <Link2 className="h-3 w-3 inline mr-1" />
                    URL match only
                  </Label>
                </div>
              </div>

              {/* Features table */}
              <div className="border rounded-md">
                {/* Table header */}
                <div className="grid grid-cols-[1fr_2fr_1fr_60px_50px] gap-2 px-3 py-2 bg-muted/50 border-b text-xs font-medium">
                  <button
                    className="flex items-center gap-1 hover:text-foreground text-left"
                    onClick={() => handleSort("feature_id")}
                  >
                    ID <SortIcon field="feature_id" />
                  </button>
                  <button
                    className="flex items-center gap-1 hover:text-foreground text-left"
                    onClick={() => handleSort("name")}
                  >
                    Name <SortIcon field="name" />
                  </button>
                  <button
                    className="flex items-center gap-1 hover:text-foreground text-left"
                    onClick={() => handleSort("category")}
                  >
                    Category <SortIcon field="category" />
                  </button>
                  <button
                    className="flex items-center gap-1 hover:text-foreground text-center justify-center"
                    onClick={() => handleSort("ui_count")}
                  >
                    UI <SortIcon field="ui_count" />
                  </button>
                  <button
                    className="flex items-center gap-1 hover:text-foreground text-center justify-center"
                    onClick={() => handleSort("url_match")}
                    title="URL Match"
                  >
                    <Link2 className="h-3 w-3" /> <SortIcon field="url_match" />
                  </button>
                </div>

                {/* Table body */}
                <ScrollArea className="h-[280px]">
                  {loadingFeatures ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                    </div>
                  ) : filteredFeatures.length === 0 ? (
                    <div className="text-center py-8 text-sm text-muted-foreground">
                      {searchQuery || urlMatchOnly
                        ? "No features match your filters"
                        : "No features with UI criteria found"}
                    </div>
                  ) : (
                    filteredFeatures.map((feature) => (
                      <button
                        key={feature.feature_id}
                        className={cn(
                          "w-full grid grid-cols-[1fr_2fr_1fr_60px_50px] gap-2 px-3 py-2 text-xs text-left",
                          "hover:bg-muted/50 border-b border-border/50 transition-colors",
                          selectedFeature === feature.feature_id &&
                            "bg-blue-500/10 hover:bg-blue-500/20"
                        )}
                        onClick={() => {
                          setSelectedFeature(feature.feature_id);
                          setSelectedCriterion("");
                        }}
                      >
                        <span className="font-mono truncate">{feature.feature_id}</span>
                        <span className="truncate">{feature.name}</span>
                        <span className="truncate text-muted-foreground">
                          {feature.category}
                        </span>
                        <span className="text-center">{feature.uiCount}</span>
                        <span className="text-center">
                          {feature.urlMatch && (
                            <Link2 className="h-3.5 w-3.5 text-green-500 mx-auto" />
                          )}
                        </span>
                      </button>
                    ))
                  )}
                </ScrollArea>
              </div>

              {/* Selected feature criteria */}
              {selectedFeatureData && (
                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">
                    Select UI Criterion for{" "}
                    <span className="font-mono">{selectedFeature}</span>:
                  </Label>
                  <div className="border rounded-md divide-y max-h-[120px] overflow-y-auto">
                    {selectedFeatureData.uiCriteria.map((criterion) => {
                      const isMatching = selectedFeatureData.matchingCriteriaIds.includes(
                        criterion.id
                      );
                      return (
                        <button
                          key={criterion.id}
                          className={cn(
                            "w-full flex items-start gap-2 px-3 py-2 text-left text-xs",
                            "hover:bg-muted/50 transition-colors",
                            selectedCriterion === criterion.id &&
                              "bg-blue-500/10 hover:bg-blue-500/20"
                          )}
                          onClick={() => setSelectedCriterion(criterion.id)}
                        >
                          <span
                            className={cn(
                              "font-mono shrink-0 mt-0.5",
                              selectedCriterion === criterion.id && "text-blue-400"
                            )}
                          >
                            {criterion.id}
                          </span>
                          <span className="flex-1 line-clamp-2">{criterion.criterion}</span>
                          {isMatching && (
                            <Link2 className="h-3.5 w-3.5 text-green-500 shrink-0 mt-0.5" />
                          )}
                          {selectedCriterion === criterion.id && (
                            <CheckCircle2 className="h-3.5 w-3.5 text-blue-400 shrink-0 mt-0.5" />
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Stats */}
              <div className="text-xs text-muted-foreground">
                {filteredFeatures.length} features
                {urlMatchOnly && ` (${processedFeatures.filter((f) => f.urlMatch).length} URL matches)`}
                {selectedFeature && selectedCriterion && (
                  <span className="ml-2 text-blue-400">
                    → {selectedFeature} / {selectedCriterion}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isCapturing}>
            Cancel
          </Button>
          <Button
            onClick={handleCapture}
            disabled={
              isCapturing ||
              (mode === "existing" && (!selectedFeature || !selectedCriterion))
            }
          >
            {isCapturing ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Capturing...
              </>
            ) : (
              <>
                <Camera className="h-4 w-4 mr-2" />
                Capture
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
