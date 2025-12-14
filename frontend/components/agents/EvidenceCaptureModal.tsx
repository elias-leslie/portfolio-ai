"use client";

import { useState, useEffect } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Camera, Loader2, Zap, FolderOpen } from "lucide-react";

interface Feature {
  feature_id: string;
  name: string;
  category: string;
  acceptance_criteria: Array<{
    id: string;
    criterion: string;
    type: string;
  }>;
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

export function EvidenceCaptureModal({
  open,
  onClose,
  pageUrl,
  onCaptured,
}: EvidenceCaptureModalProps) {
  const [mode, setMode] = useState<"quick" | "existing">("quick");
  const [selectedFeature, setSelectedFeature] = useState<string>("");
  const [selectedCriterion, setSelectedCriterion] = useState<string>("");

  // Fetch existing features for dropdown
  const { data: featuresData, isLoading: loadingFeatures } = useQuery<{
    features: Feature[];
  }>({
    queryKey: ["features-for-evidence"],
    queryFn: async () => {
      const response = await fetch("/api/capabilities/features?limit=100");
      if (!response.ok) throw new Error("Failed to fetch features");
      return response.json();
    },
    enabled: open && mode === "existing",
  });

  // Get selected feature's criteria
  const selectedFeatureData = featuresData?.features.find(
    (f) => f.feature_id === selectedFeature
  );
  const uiCriteria =
    selectedFeatureData?.acceptance_criteria.filter((c) => c.type === "ui") ||
    [];

  // Reset state when modal opens/closes
  useEffect(() => {
    if (!open) {
      setMode("quick");
      setSelectedFeature("");
      setSelectedCriterion("");
    }
  }, [open]);

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
    if (mode === "quick") {
      // Create quick feature, then capture
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
      // Use existing feature
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

  const isCapturing =
    quickFeatureMutation.isPending || captureMutation.isPending;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Camera className="h-5 w-5" />
            Capture Evidence
          </DialogTitle>
          <DialogDescription>
            Capture a screenshot and page state for: {pageUrl}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Mode selector */}
          <div className="flex gap-2">
            <Button
              variant={mode === "quick" ? "default" : "outline"}
              size="sm"
              onClick={() => setMode("quick")}
              className="flex-1"
            >
              <Zap className="h-4 w-4 mr-2" />
              Quick Capture
            </Button>
            <Button
              variant={mode === "existing" ? "default" : "outline"}
              size="sm"
              onClick={() => setMode("existing")}
              className="flex-1"
            >
              <FolderOpen className="h-4 w-4 mr-2" />
              Link to Feature
            </Button>
          </div>

          {mode === "quick" ? (
            <div className="rounded-lg border border-border bg-muted/30 p-4 text-sm text-muted-foreground">
              <p>
                Creates a debug feature (
                <code className="text-xs bg-muted px-1 rounded">
                  FEAT-DEBUG-*
                </code>
                ) and captures evidence immediately.
              </p>
              <p className="mt-2">Debug features appear in the Features tab for review.</p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="feature">Feature</Label>
                <Select
                  value={selectedFeature}
                  onValueChange={(v) => {
                    setSelectedFeature(v);
                    setSelectedCriterion("");
                  }}
                >
                  <SelectTrigger id="feature">
                    <SelectValue placeholder="Select a feature..." />
                  </SelectTrigger>
                  <SelectContent>
                    {loadingFeatures ? (
                      <SelectItem value="_loading" disabled>
                        Loading...
                      </SelectItem>
                    ) : (
                      featuresData?.features.map((f) => (
                        <SelectItem key={f.feature_id} value={f.feature_id}>
                          {f.feature_id}: {f.name}
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>

              {selectedFeature && (
                <div className="space-y-2">
                  <Label htmlFor="criterion">UI Criterion</Label>
                  <Select
                    value={selectedCriterion}
                    onValueChange={setSelectedCriterion}
                  >
                    <SelectTrigger id="criterion">
                      <SelectValue placeholder="Select a criterion..." />
                    </SelectTrigger>
                    <SelectContent>
                      {uiCriteria.length === 0 ? (
                        <SelectItem value="_none" disabled>
                          No UI criteria found
                        </SelectItem>
                      ) : (
                        uiCriteria.map((c) => (
                          <SelectItem key={c.id} value={c.id}>
                            {c.id}: {c.criterion.slice(0, 50)}
                            {c.criterion.length > 50 ? "..." : ""}
                          </SelectItem>
                        ))
                      )}
                    </SelectContent>
                  </Select>
                </div>
              )}
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
