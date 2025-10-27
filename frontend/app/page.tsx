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
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">
            Portfolio AI Dashboard
          </h1>
          <p className="mt-2 text-sm text-gray-600">
            AI-powered portfolio intelligence and market insights
          </p>
        </div>

        {/* Market Conditions */}
        <div className="mb-8">
          <MarketConditions />
        </div>

        {/* Portfolio Overview */}
        <div className="mb-8">
          <h2 className="text-xl font-semibold mb-4">Portfolio Overview</h2>
          <PortfolioOverview />
        </div>

        {/* Investment Ideas */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold">Investment Ideas</h2>
            <div className="flex gap-2">
              <select
                value={agentType}
                onChange={(e) =>
                  setAgentType(e.target.value as "discovery" | "portfolio_analyzer")
                }
                className="px-3 py-2 border rounded-md text-sm"
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
                  className="h-48 animate-pulse bg-gray-200 rounded-lg"
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
            <div className="text-center py-12 bg-white rounded-lg border">
              <p className="text-gray-500 mb-4">
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
