"use client";

import { Globe, CheckCircle2, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { HealthResponse } from "@/lib/api/status";

interface APIQuotasCardProps {
  health: HealthResponse;
}

export function APIQuotasCard({ health }: APIQuotasCardProps) {
  const quotas = health.api_quotas || [];

  if (quotas.length === 0) {
    return null;
  }

  const configuredCount = quotas.filter((q) => q.configured).length;

  return (
    <Card className="border-border">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Globe className="h-5 w-5" />
            <span>API Quotas & Configuration</span>
          </div>
          <Badge variant={configuredCount === quotas.length ? "default" : "secondary"}>
            {configuredCount}/{quotas.length} Configured
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {quotas
            .sort((a, b) => a.source_name.localeCompare(b.source_name))
            .map((quota) => (
              <div
                key={quota.source_name}
                className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-3 flex-1">
                  {quota.configured ? (
                    <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
                  ) : (
                    <XCircle className="h-4 w-4 text-gray-400 flex-shrink-0" />
                  )}
                  <div className="flex-1">
                    <div className="font-medium capitalize">
                      {quota.source_name.replace(/_/g, " ")}
                    </div>
                    <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground mt-1">
                      {quota.rate_limit && (
                        <div>Rate limit: {quota.rate_limit}</div>
                      )}
                      {quota.daily_limit && (
                        <div>Daily limit: {quota.daily_limit}</div>
                      )}
                      {quota.estimated_capacity !== null && quota.estimated_capacity !== undefined && (
                        <div>
                          Estimated capacity: ~{quota.estimated_capacity} tickers (15-min refresh)
                        </div>
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
        <div className="mt-4 p-3 bg-muted/50 rounded-lg text-xs text-muted-foreground">
          <p className="font-medium mb-1">Note:</p>
          <p>
            API keys are configured via environment variables. Sources marked as "Not Configured" will
            not be used for data fetching. Estimated capacity assumes a 15-minute refresh interval and
            accounts for rate limits and daily quotas.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
