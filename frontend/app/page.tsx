"use client";

import { useState } from "react";
import { MarketConditions } from "@/components/portfolio/MarketConditions";
import { PortfolioOverview } from "@/components/portfolio/PortfolioOverview";
import { IdeaCard } from "@/components/portfolio/IdeaCard";
import { useIdeas, useGenerateIdeas } from "@/lib/hooks/useIdeas";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export default function Dashboard() {
  const { data: ideasData, isLoading: ideasLoading } = useIdeas({
    status: "pending",
    limit: 5,
  });
  const generateIdeas = useGenerateIdeas();
  const [agentType, setAgentType] = useState<"discovery" | "portfolio_analyzer">(
    "discovery"
  );

  const handleGenerateIdeas = () => {
    generateIdeas.mutate(
      { agent_type: agentType },
      {
        onSuccess: (data) => {
          toast.success(
            `Successfully generated ${data.num_ideas} new ideas!`
          );
        },
        onError: (error) => {
          toast.error(`Failed to generate ideas: ${error.message}`);
        },
      }
    );
  };

  return (
    <div className="bg-bg">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-10">
          <h1 className="text-3xl font-semibold text-text">
            Portfolio AI Dashboard
          </h1>
          <p className="mt-2 text-sm text-text-muted">
            AI-powered portfolio intelligence and market insights
          </p>
        </div>

        {/* Market Conditions */}
        <div className="mb-10">
          <MarketConditions />
        </div>

        {/* Portfolio Overview */}
        <div className="mb-10 space-y-4">
          <h2 className="text-xl font-semibold text-text">Portfolio Overview</h2>
          <PortfolioOverview />
        </div>

        {/* Investment Ideas */}
        <div className="mb-12">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
            <h2 className="text-xl font-semibold text-text">Investment Ideas</h2>
            <div className="flex items-center gap-3">
              <select
                value={agentType}
                onChange={(e) =>
                  setAgentType(e.target.value as "discovery" | "portfolio_analyzer")
                }
                className="rounded-md border border-border bg-surface/80 px-3 py-2 text-sm text-text shadow-xs transition-colors duration-200 ease-in-out focus-visible:border-focus focus-visible:ring-2 focus-visible:ring-focus/30 disabled:cursor-not-allowed disabled:opacity-35"
                disabled={generateIdeas.isPending}
              >
                <option value="discovery">General Market Ideas</option>
                <option value="portfolio_analyzer">Portfolio-Specific Ideas</option>
              </select>
              <Button
                onClick={handleGenerateIdeas}
                disabled={generateIdeas.isPending}
              >
                {generateIdeas.isPending ? "Generating..." : "Generate New Ideas"}
              </Button>
            </div>
          </div>

          {ideasLoading ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {[...Array(3)].map((_, i) => (
                <div
                  key={i}
                  className="h-48 animate-pulse rounded-lg bg-surface-muted/60"
                />
              ))}
            </div>
          ) : ideasData?.ideas.length ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {ideasData.ideas.map((idea) => (
                <IdeaCard key={idea.id} idea={idea} />
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-surface-elev py-12 text-center shadow-md">
              <p className="mb-4 text-text-muted">
                No investment ideas yet. Generate some to get started!
              </p>
              <Button onClick={handleGenerateIdeas}>
                Generate Your First Ideas
              </Button>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
