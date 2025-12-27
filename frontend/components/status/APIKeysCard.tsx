"use client";

import { Key, CheckCircle2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { APIKeyStatusInfo } from "@/lib/api/status";
import { ExpandableCard } from "@/components/status/ExpandableCard";

interface APIKeysCardProps {
    apiKeys: APIKeyStatusInfo[];
}

export function APIKeysCard({ apiKeys }: APIKeysCardProps) {
    if (!apiKeys || apiKeys.length === 0) {
        return null;
    }

    const configuredCount = apiKeys.filter((k) => k.configured).length;

    const summary = `${configuredCount}/${apiKeys.length} configured`;

    return (
        <ExpandableCard
            title={
                <div className="flex items-center gap-2">
                    <Key className="h-5 w-5" />
                    <span>API Key Configuration</span>
                </div>
            }
            description="Environment variables required for upstream data providers."
            summary={summary}
            defaultCollapsed
        >
            <div className="space-y-3">
                {apiKeys
                    .sort((a, b) => a.source.localeCompare(b.source))
                    .map((key) => (
                        <div
                            key={key.source}
                            className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50 transition-colors"
                        >
                            <div className="flex items-center gap-3 flex-1">
                                {key.configured ? (
                                    <CheckCircle2 className="h-4 w-4 text-gain flex-shrink-0" />
                                ) : (
                                    <XCircle className="h-4 w-4 text-text-muted flex-shrink-0" />
                                )}
                                <div className="flex-1">
                                    <div className="font-medium capitalize">
                                        {key.source.replace(/_/g, " ")}
                                    </div>
                                    <div className="text-xs text-muted-foreground mt-1">
                                        Env var: <code className="text-xs">{key.envVar}</code>
                                    </div>
                                </div>
                            </div>
                            <div>
                                {key.configured ? (
                                    <Badge className="bg-green-500 text-white">
                                        Active
                                    </Badge>
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
                    API keys are configured via environment variables. Sources marked as
                    &quot;Not Configured&quot; will not be used for data fetching. Set the environment
                    variable and restart services to activate a source.
                </p>
            </div>
        </ExpandableCard>
    );
}
