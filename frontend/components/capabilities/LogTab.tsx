/**
 * LogTab - Claude Session Progress Log viewer
 * Shows session progress entries with expandable rows, filters, and pagination
 */

"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  ChevronDown,
  ChevronRight,
  Loader2,
  RefreshCw,
  Clock,
  FileCode,
} from "lucide-react";

interface ProgressEntry {
  id: number;
  session_id: string | null;
  logged_at: string;
  action: string;
  action_type: string | null;
  feature_id: string | null;
  task_file: string | null;
  files_modified: string[] | null;
  details: Record<string, unknown> | null;
  git_commit: string | null;
  context_percent: number | null;
}

interface ProgressResponse {
  entries: ProgressEntry[];
  limit: number;
  offset: number;
}

const ACTION_TYPE_COLORS: Record<string, string> = {
  start: "bg-green-500/20 text-green-700 dark:text-green-400",
  progress: "bg-blue-500/20 text-blue-700 dark:text-blue-400",
  complete: "bg-emerald-500/20 text-emerald-700 dark:text-emerald-400",
  verify: "bg-purple-500/20 text-purple-700 dark:text-purple-400",
  audit: "bg-orange-500/20 text-orange-700 dark:text-orange-400",
  pause: "bg-yellow-500/20 text-yellow-700 dark:text-yellow-400",
  plan: "bg-indigo-500/20 text-indigo-700 dark:text-indigo-400",
  test: "bg-gray-500/20 text-gray-700 dark:text-gray-400",
  commit: "bg-cyan-500/20 text-cyan-700 dark:text-cyan-400",
  checkpoint: "bg-amber-500/20 text-amber-700 dark:text-amber-400",
};

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

function ExpandableRow({ entry }: { entry: ProgressEntry }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <TableRow
        className="cursor-pointer hover:bg-muted/50"
        onClick={() => setExpanded(!expanded)}
      >
        <TableCell>
          <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
            {expanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </Button>
        </TableCell>
        <TableCell className="text-xs text-muted-foreground">
          {formatDate(entry.logged_at)}
        </TableCell>
        <TableCell className="max-w-[300px] truncate" title={entry.action}>
          {entry.action}
        </TableCell>
        <TableCell>
          {entry.action_type && (
            <Badge
              variant="secondary"
              className={ACTION_TYPE_COLORS[entry.action_type] || ""}
            >
              {entry.action_type}
            </Badge>
          )}
        </TableCell>
        <TableCell>
          {entry.feature_id && (
            <Badge variant="outline">{entry.feature_id}</Badge>
          )}
        </TableCell>
        <TableCell className="text-xs">
          {entry.task_file && (
            <span className="text-muted-foreground" title={entry.task_file}>
              {entry.task_file.split("/").pop()}
            </span>
          )}
        </TableCell>
        <TableCell className="text-xs">
          {entry.git_commit && (
            <code className="bg-muted px-1 py-0.5 rounded text-[10px]">
              {entry.git_commit.slice(0, 7)}
            </code>
          )}
        </TableCell>
      </TableRow>

      {expanded && (
        <TableRow className="bg-muted/30">
          <TableCell colSpan={7} className="p-0">
            <div className="py-4 px-6 space-y-4 text-sm">
              {/* Session & Context Row */}
              <div className="flex flex-wrap gap-x-8 gap-y-2">
                {entry.session_id && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground text-xs font-medium">Session:</span>
                    <code className="font-mono text-xs bg-muted px-2 py-1 rounded">
                      {entry.session_id}
                    </code>
                  </div>
                )}
                {entry.context_percent !== null && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground text-xs font-medium">Context:</span>
                    <Badge variant="outline" className="text-xs">
                      {entry.context_percent}%
                    </Badge>
                  </div>
                )}
              </div>

              {/* Full Action Text */}
              {entry.action && entry.action.length > 50 && (
                <div className="space-y-1">
                  <span className="text-muted-foreground text-xs font-medium">Full Action:</span>
                  <div className="text-sm bg-muted/50 px-3 py-2 rounded border max-h-60 overflow-y-auto whitespace-pre-wrap break-words">
                    {entry.action}
                  </div>
                </div>
              )}

              {/* Files Modified */}
              {entry.files_modified && entry.files_modified.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <FileCode className="h-3 w-3 text-muted-foreground" />
                    <span className="text-muted-foreground text-xs font-medium">
                      Files Modified ({entry.files_modified.length}):
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {entry.files_modified.map((file, i) => (
                      <code key={i} className="bg-muted px-2 py-1 rounded text-xs border">
                        {file.split("/").pop()}
                      </code>
                    ))}
                  </div>
                </div>
              )}

              {/* Details JSON */}
              {entry.details && Object.keys(entry.details).length > 0 && (
                <div className="space-y-1">
                  <span className="text-muted-foreground text-xs font-medium">Details:</span>
                  <pre className="bg-muted p-3 rounded text-xs overflow-x-auto border max-h-40 overflow-y-auto">
                    {JSON.stringify(entry.details, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

export function LogTab() {
  const [sessionFilter, setSessionFilter] = useState<string>("");
  const [featureFilter, setFeatureFilter] = useState<string>("");
  const [actionTypeFilter, setActionTypeFilter] = useState<string>("all");
  const [page, setPage] = useState(0);
  const pageSize = 25;

  const { data, isLoading, refetch, isRefetching } = useQuery<ProgressResponse>({
    queryKey: [
      "claude-progress",
      sessionFilter,
      featureFilter,
      actionTypeFilter,
      page,
    ],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("limit", String(pageSize));
      params.set("offset", String(page * pageSize));
      if (sessionFilter) params.set("session_id", sessionFilter);
      if (featureFilter) params.set("feature_id", featureFilter);
      if (actionTypeFilter !== "all") params.set("action_type", actionTypeFilter);

      const response = await fetch(`/api/claude/progress?${params}`);
      if (!response.ok) throw new Error("Failed to fetch progress");
      return response.json();
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const entries = data?.entries || [];
  const hasMore = entries.length === pageSize;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Claude Session Log
            </CardTitle>
            <CardDescription>
              Track Claude Code session progress and actions
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isRefetching}
          >
            {isRefetching ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {/* Filters */}
        <div className="flex flex-wrap gap-3 mb-4">
          <Input
            placeholder="Filter by session ID..."
            value={sessionFilter}
            onChange={(e) => {
              setSessionFilter(e.target.value);
              setPage(0);
            }}
            className="w-[200px]"
          />
          <Input
            placeholder="Filter by feature ID..."
            value={featureFilter}
            onChange={(e) => {
              setFeatureFilter(e.target.value);
              setPage(0);
            }}
            className="w-[150px]"
          />
          <Select
            value={actionTypeFilter}
            onValueChange={(val) => {
              setActionTypeFilter(val);
              setPage(0);
            }}
          >
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="Action Type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              <SelectItem value="commit">Commit</SelectItem>
              <SelectItem value="checkpoint">Checkpoint</SelectItem>
              <SelectItem value="start">Start</SelectItem>
              <SelectItem value="progress">Progress</SelectItem>
              <SelectItem value="complete">Complete</SelectItem>
              <SelectItem value="verify">Verify</SelectItem>
              <SelectItem value="audit">Audit</SelectItem>
              <SelectItem value="pause">Pause</SelectItem>
              <SelectItem value="plan">Plan</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Table */}
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : entries.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            No progress entries found
          </div>
        ) : (
          <>
            <div className="border rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-8"></TableHead>
                    <TableHead className="w-[130px]">Time</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead className="w-[100px]">Type</TableHead>
                    <TableHead className="w-[100px]">Feature</TableHead>
                    <TableHead className="w-[100px]">Task File</TableHead>
                    <TableHead className="w-[80px]">Commit</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {entries.map((entry) => (
                    <ExpandableRow key={entry.id} entry={entry} />
                  ))}
                </TableBody>
              </Table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between mt-4">
              <span className="text-sm text-muted-foreground">
                Page {page + 1}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(Math.max(0, page - 1))}
                  disabled={page === 0}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(page + 1)}
                  disabled={!hasMore}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
