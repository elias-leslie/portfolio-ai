"use client";

import { Globe, CheckCircle2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { HealthResponse } from "@/lib/api/status";
import { ExpandableCard } from "@/components/status/ExpandableCard";

interface APIQuotasCardProps {
  health: HealthResponse;
}

export function APIQuotasCard({ health }: APIQuotasCardProps) {
  const quotas = health.api_quotas || [];

  if (!quotas.length) {
    return null;
  }

  const configuredCount = quotas.filter((q) => q.configured).length;
  const summary = `${configuredCount}/${quotas.length} configured`;

  return (
    <ExpandableCard
      title={
        <div className="flex items-center gap-2">
          <Globe className="h-5 w-5" />
          <span>API Quotas & Configuration</span>
        </div>
      }
      description="Rate limits, daily quotas, and overall capacity for upstream APIs."
      summary={summary}
      defaultCollapsed
    >
      <div className="space-y-3">
        {quotas
          .sort((a, b) => a.source_name.localeCompare(b.source_name))
          .map((quota) => (
            <div
              key={quota.source_name}
              className="flex items-center justify-between rounded-lg border p-3 transition-colors hover:bg-muted/50"
            >
              <div className="flex flex-1 items-center gap-3">
                {quota.configured ? (
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                ) : (
                  <XCircle className="h-4 w-4 text-gray-400" />
                )}
                <div className="flex-1">
                  <div className="font-medium capitalize">
                    {quota.source_name.replace(/_/g, " ")}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                    {quota.rate_limit && <div>Rate limit: {quota.rate_limit}</div>}
                    {quota.daily_limit && <div>Daily limit: {quota.daily_limit}</div>}
                    {quota.estimated_capacity !== null &&
                      quota.estimated_capacity !== undefined && (
                        <div>Estimated capacity: ~{quota.estimated_capacity} tickers</div>
                      )}
                  </div>
                </div>
              </div>
              <div>
                {quota.configured ? (
                  <Badge className="bg-green-500 text-white">Active</Badge>
                ) : (
                  <Badge variant="outline">Not Configured</Badge>
                )}
              </div>
            </div>
          ))}
      </div>
      <p className="mt-4 text-xs text-muted-foreground">
        Sources marked as "Not Configured" will be skipped. Configure their environment variables and restart services to activate them.
      </p>
    </ExpandableCard>
  );
}
