"use client";

import { useParams, useRouter } from "next/navigation";
import { useIdeaDetails, useUpdateIdeaStatus } from "@/lib/hooks/useIdeas";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ArrowLeft, TrendingUp, AlertTriangle, Target } from "lucide-react";

export default function IdeaDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const ideaId = params.id as string;

  const { data: idea, isLoading } = useIdeaDetails(ideaId);
  const updateStatus = useUpdateIdeaStatus();

  const handleStatusChange = (
    status: "pending" | "validated" | "executed" | "rejected"
  ) => {
    updateStatus.mutate(
      { ideaId, data: { status } },
      {
        onSuccess: () => {
          toast.success(`Status updated to ${status}!`);
        },
        onError: (error) => {
          toast.error(`Failed to update status: ${error.message}`);
        },
      }
    );
  };

  const getRiskStyles = (risk: string) => {
    switch (risk.toLowerCase()) {
      case "low":
        return "bg-gain/15 text-gain-strong border border-gain/30";
      case "medium":
        return "bg-primary/15 text-primary border border-primary/30";
      case "high":
        return "bg-loss/15 text-loss-strong border border-loss/35";
      default:
        return "bg-surface-muted/70 text-text-muted border border-border";
    }
  };

  const getConfidenceClass = (score: number) => {
    if (score >= 0.8) return "text-gain";
    if (score >= 0.6) return "text-primary";
    return "text-loss";
  };

  const getStatusStyles = (status: string) => {
    switch (status) {
      case "pending":
        return "bg-neutral/20 text-text";
      case "validated":
        return "bg-gain/20 text-gain-strong";
      case "executed":
        return "bg-primary/20 text-primary";
      case "rejected":
        return "bg-loss/20 text-loss-strong";
      default:
        return "bg-surface-muted/70 text-text-muted";
    }
  };

  if (isLoading) {
    return (
      <div className="bg-bg">
        <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
          <div className="animate-pulse space-y-6">
            <div className="h-9 w-48 rounded-md bg-surface-muted/60" />
            <div className="h-12 w-3/4 rounded-md bg-surface-muted/60" />
            <div className="h-64 rounded-lg bg-surface-muted/60" />
            <div className="grid gap-4 md:grid-cols-2">
              <div className="h-48 rounded-lg bg-surface-muted/60" />
              <div className="h-48 rounded-lg bg-surface-muted/60" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!idea) {
    return (
      <div className="bg-bg">
        <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
          <div className="py-12 text-center">
            <h2 className="mb-2 text-2xl font-semibold text-text">
              Idea Not Found
            </h2>
            <p className="mb-6 text-text-muted">
              The investment idea you&rsquo;re looking for doesn&rsquo;t exist.
            </p>
            <Button onClick={() => router.push("/")}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Dashboard
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-bg">
      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
        {/* Back Button */}
        <Button
          variant="ghost"
          className="mb-6"
          onClick={() => router.push("/")}
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Dashboard
        </Button>

        {/* Header */}
        <div className="mb-8">
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <span
                  className={`rounded-full px-3 py-1 text-xs font-medium ${getStatusStyles(
                    idea.status
                  )}`}
                >
                  {idea.status.toUpperCase()}
                </span>
                <span
                  className={`rounded-full px-3 py-1 text-xs font-medium ${getRiskStyles(
                    idea.risk_level
                  )}`}
                >
                  {idea.risk_level.toUpperCase()} RISK
                </span>
                <span className="text-xs text-text-muted">
                  {idea.idea_type}
                </span>
              </div>
              <h1 className="mb-2 text-3xl font-semibold text-text">
                {idea.title}
              </h1>
              <div className="flex items-center gap-4 text-sm text-text-muted">
                <div className="flex items-center gap-2">
                  <span>Confidence:</span>
                  <span
                    className={`text-lg font-semibold ${getConfidenceClass(
                      idea.confidence_score
                    )}`}
                  >
                    {(idea.confidence_score * 100).toFixed(0)}%
                  </span>
                </div>
                {idea.reward_estimate && (
                  <div className="flex items-center gap-2">
                    <TrendingUp className="h-4 w-4 text-gain" />
                    <span className="font-medium text-gain">
                      {idea.reward_estimate}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="space-y-6">
          {/* Thesis */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="h-5 w-5" />
                Investment Thesis
              </CardTitle>
              <CardDescription>
                The rationale behind this investment opportunity
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="whitespace-pre-wrap text-text leading-relaxed">
                {idea.thesis}
              </p>
            </CardContent>
          </Card>

          {/* Action */}
          <Card>
            <CardHeader>
              <CardTitle>Recommended Action</CardTitle>
              <CardDescription>
                What you should do to capitalize on this opportunity
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="font-medium text-text">{idea.action}</p>
            </CardContent>
          </Card>

          {/* Portfolio Impact & Data Needed */}
          <div className="grid gap-6 md:grid-cols-2">
            {idea.portfolio_impact && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Portfolio Impact</CardTitle>
                  <CardDescription>
                    How this idea relates to your current holdings
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="whitespace-pre-wrap text-sm text-text">
                    {idea.portfolio_impact}
                  </p>
                </CardContent>
              </Card>
            )}

            {idea.data_needed && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Data Needed</CardTitle>
                  <CardDescription>
                    Information to gather before acting
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="whitespace-pre-wrap text-sm text-text">
                    {idea.data_needed}
                  </p>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Risks */}
          {idea.risks && (
            <Card className="border border-loss/35 bg-loss/10">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-loss-strong">
                  <AlertTriangle className="h-5 w-5" aria-hidden />
                  Risks & Considerations
                </CardTitle>
                <CardDescription className="text-loss-strong/80">
                  Important factors to consider before proceeding
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="whitespace-pre-wrap text-sm text-loss-strong">
                  {idea.risks}
                </p>
              </CardContent>
            </Card>
          )}

          {/* Status Actions */}
          <Card>
            <CardHeader>
              <CardTitle>Update Status</CardTitle>
              <CardDescription>
                Track the progress of this investment idea
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant={idea.status === "pending" ? "default" : "outline"}
                  onClick={() => handleStatusChange("pending")}
                  disabled={updateStatus.isPending}
                >
                  Pending Review
                </Button>
                <Button
                  variant={idea.status === "validated" ? "default" : "outline"}
                  onClick={() => handleStatusChange("validated")}
                  disabled={updateStatus.isPending}
                >
                  Validated
                </Button>
                <Button
                  variant={idea.status === "executed" ? "default" : "outline"}
                  onClick={() => handleStatusChange("executed")}
                  disabled={updateStatus.isPending}
                >
                  Executed
                </Button>
                <Button
                  variant={idea.status === "rejected" ? "destructive" : "outline"}
                  onClick={() => handleStatusChange("rejected")}
                  disabled={updateStatus.isPending}
                >
                  Rejected
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Metadata */}
          <Card className="bg-surface-muted/60">
            <CardContent className="pt-6">
              <div className="grid gap-2 text-xs text-text-muted">
                <div className="flex justify-between">
                  <span>Created:</span>
                  <span>
                    {new Date(idea.created_at).toLocaleDateString("en-US", {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Last Updated:</span>
                  <span>
                    {new Date(idea.updated_at).toLocaleDateString("en-US", {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Agent Run ID:</span>
                  <span className="font-mono">{idea.agent_run_id}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
