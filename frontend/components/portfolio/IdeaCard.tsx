"use client";

import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Idea } from "@/lib/api/ideas";

interface IdeaCardProps {
  idea: Idea;
}

export function IdeaCard({ idea }: IdeaCardProps) {
  const getRiskStyles = (risk: string) => {
    switch (risk.toLowerCase()) {
      case "low":
        return "bg-gain/15 text-gain-strong";
      case "medium":
        return "bg-primary/15 text-primary";
      case "high":
        return "bg-loss/15 text-loss-strong";
      default:
        return "bg-surface-muted/70 text-text-muted";
    }
  };

  const getConfidenceColor = (score: number) => {
    if (score >= 0.8) return "bg-gain";
    if (score >= 0.6) return "bg-primary";
    return "bg-loss";
  };

  return (
    <Link href={`/ideas/${idea.id}`}>
      <Card className="cursor-pointer p-4 transition-shadow duration-200 ease-in-out hover:shadow-md">
        <div className="mb-2 flex items-start justify-between gap-3">
          <h3 className="line-clamp-2 text-sm font-semibold text-text">{idea.title}</h3>
          <span
            className={`rounded-full px-2 py-1 text-xs font-medium ${getRiskStyles(
              idea.risk_level
            )}`}
          >
            {idea.risk_level}
          </span>
        </div>

        <p className="mb-3 line-clamp-2 text-xs text-text-muted">
          {idea.thesis}
        </p>

        <div className="flex items-center justify-between text-xs text-text-muted">
          <div className="flex items-center gap-2">
            <span>Confidence:</span>
            <div className="flex items-center gap-1 text-text">
              <div className="h-2 w-16 overflow-hidden rounded-full bg-surface-muted/60">
                <div
                  className={`h-full ${getConfidenceColor(
                    idea.confidence_score
                  )}`}
                  style={{ width: `${idea.confidence_score * 100}%` }}
                />
              </div>
              <span className="font-medium text-text">
                {(idea.confidence_score * 100).toFixed(0)}%
              </span>
            </div>
          </div>
          {idea.reward_estimate && (
            <span className="font-medium text-gain">
              {idea.reward_estimate}
            </span>
          )}
        </div>

        <div className="mt-3 text-xs text-text-muted">
          <span>Action: </span>
          <span className="font-medium text-text">{idea.action}</span>
        </div>
      </Card>
    </Link>
  );
}
