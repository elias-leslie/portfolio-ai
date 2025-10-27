"use client";

import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Idea } from "@/lib/api/ideas";

interface IdeaCardProps {
  idea: Idea;
}

export function IdeaCard({ idea }: IdeaCardProps) {
  const getRiskColor = (risk: string) => {
    switch (risk.toLowerCase()) {
      case "low":
        return "bg-green-100 text-green-800";
      case "medium":
        return "bg-yellow-100 text-yellow-800";
      case "high":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const getConfidenceColor = (score: number) => {
    if (score >= 0.8) return "bg-green-500";
    if (score >= 0.6) return "bg-yellow-500";
    return "bg-red-500";
  };

  return (
    <Link href={`/ideas/${idea.id}`}>
      <Card className="p-4 hover:shadow-lg transition-shadow cursor-pointer">
        <div className="flex items-start justify-between mb-2">
          <h3 className="font-semibold text-sm line-clamp-2">{idea.title}</h3>
          <span
            className={`px-2 py-1 text-xs rounded-full ${getRiskColor(
              idea.risk_level
            )}`}
          >
            {idea.risk_level}
          </span>
        </div>

        <p className="text-xs text-muted-foreground line-clamp-2 mb-3">
          {idea.thesis}
        </p>

        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">Confidence:</span>
            <div className="flex items-center gap-1">
              <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className={`h-full ${getConfidenceColor(
                    idea.confidence_score
                  )}`}
                  style={{ width: `${idea.confidence_score * 100}%` }}
                />
              </div>
              <span className="font-medium">
                {(idea.confidence_score * 100).toFixed(0)}%
              </span>
            </div>
          </div>
          {idea.reward_estimate && (
            <span className="font-medium text-green-600">
              {idea.reward_estimate}
            </span>
          )}
        </div>

        <div className="mt-3 text-xs">
          <span className="text-muted-foreground">Action: </span>
          <span className="font-medium">{idea.action}</span>
        </div>
      </Card>
    </Link>
  );
}
