"use client";

import { useParams, useRouter } from "next/navigation";
import { useIdeaDetails, useUpdateIdeaStatus } from "@/lib/hooks/useIdeas";
import { Button } from "@/components/ui/button";
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
    updateStatus.mutate({ ideaId, data: { status } });
  };

  const getRiskColor = (risk: string) => {
    switch (risk.toLowerCase()) {
      case "low":
        return "bg-green-100 text-green-800 border-green-200";
      case "medium":
        return "bg-yellow-100 text-yellow-800 border-yellow-200";
      case "high":
        return "bg-red-100 text-red-800 border-red-200";
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  const getConfidenceColor = (score: number) => {
    if (score >= 0.8) return "text-green-600";
    if (score >= 0.6) return "text-yellow-600";
    return "text-red-600";
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "pending":
        return "bg-blue-100 text-blue-800";
      case "validated":
        return "bg-green-100 text-green-800";
      case "executed":
        return "bg-purple-100 text-purple-800";
      case "rejected":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
          <div className="animate-pulse space-y-6">
            <div className="h-8 w-48 bg-gray-200 rounded" />
            <div className="h-12 w-3/4 bg-gray-200 rounded" />
            <div className="h-64 bg-gray-200 rounded" />
            <div className="grid gap-4 md:grid-cols-2">
              <div className="h-48 bg-gray-200 rounded" />
              <div className="h-48 bg-gray-200 rounded" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!idea) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
          <div className="text-center py-12">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Idea Not Found
            </h2>
            <p className="text-gray-600 mb-6">
              The investment idea you're looking for doesn't exist.
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
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
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
                  className={`px-3 py-1 text-xs font-medium rounded-full ${getStatusColor(
                    idea.status
                  )}`}
                >
                  {idea.status.toUpperCase()}
                </span>
                <span
                  className={`px-3 py-1 text-xs font-medium rounded-full border ${getRiskColor(
                    idea.risk_level
                  )}`}
                >
                  {idea.risk_level.toUpperCase()} RISK
                </span>
                <span className="text-xs text-muted-foreground">
                  {idea.idea_type}
                </span>
              </div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">
                {idea.title}
              </h1>
              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                  <span>Confidence:</span>
                  <span
                    className={`text-lg font-bold ${getConfidenceColor(
                      idea.confidence_score
                    )}`}
                  >
                    {(idea.confidence_score * 100).toFixed(0)}%
                  </span>
                </div>
                {idea.reward_estimate && (
                  <div className="flex items-center gap-2">
                    <TrendingUp className="h-4 w-4 text-green-600" />
                    <span className="font-medium text-green-600">
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
              <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">
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
              <p className="text-gray-700 font-medium">{idea.action}</p>
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
                  <p className="text-sm text-gray-700 whitespace-pre-wrap">
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
                  <p className="text-sm text-gray-700 whitespace-pre-wrap">
                    {idea.data_needed}
                  </p>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Risks */}
          {idea.risks && (
            <Card className="border-orange-200 bg-orange-50/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-orange-900">
                  <AlertTriangle className="h-5 w-5" />
                  Risks & Considerations
                </CardTitle>
                <CardDescription className="text-orange-700">
                  Important factors to consider before proceeding
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-orange-900 whitespace-pre-wrap">
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
              {updateStatus.isSuccess && (
                <p className="mt-3 text-sm text-green-600">
                  Status updated successfully!
                </p>
              )}
            </CardContent>
          </Card>

          {/* Metadata */}
          <Card className="bg-gray-50">
            <CardContent className="pt-6">
              <div className="grid gap-2 text-xs text-muted-foreground">
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
