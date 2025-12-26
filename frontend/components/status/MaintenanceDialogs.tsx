"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle2,
  AlertCircle,
  Loader2,
} from "lucide-react";

// Reusable component for rendering task results as clean tables
export function TaskResultDisplay({ result }: { result: Record<string, unknown> }) {
  // Skip internal/meta fields
  const skipFields = ["task_id", "success", "dry_run", "duration_seconds"];
  // Detail array fields (render as table at bottom)
  const detailFields = ["details", "checks", "would_delete", "would_rotate", "tables_to_vacuum", "partitions"];

  // Separate summary fields from detail arrays
  const summaryEntries = Object.entries(result).filter(
    ([k, v]) => !skipFields.includes(k) && !detailFields.includes(k) && !Array.isArray(v)
  );
  const detailEntry = Object.entries(result).find(
    ([k, v]) => detailFields.includes(k) && Array.isArray(v) && (v as unknown[]).length > 0
  );

  return (
    <div className="space-y-3">
      {/* Summary table - key/value pairs */}
      {summaryEntries.length > 0 && (
        <div className="bg-background/50 rounded overflow-hidden">
          <table className="w-full text-sm">
            <tbody>
              {summaryEntries.map(([key, value]) => (
                <tr key={key} className="border-b border-border/20 last:border-0">
                  <td className="p-2 text-muted-foreground capitalize w-1/3">
                    {key.replace(/_/g, " ")}
                  </td>
                  <td className="p-2 font-mono font-medium">
                    {typeof value === "boolean"
                      ? (value ? "Yes" : "No")
                      : typeof value === "number"
                      ? value.toLocaleString()
                      : String(value)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Details table - array data */}
      {detailEntry && (() => {
        const [, items] = detailEntry;
        const arr = items as Array<Record<string, unknown>>;
        const firstItem = arr[0];
        const isObjectArray = typeof firstItem === "object" && firstItem !== null;
        const columns = isObjectArray ? Object.keys(firstItem) : null;

        return (
          <div>
            <div className="text-sm font-medium mb-2">
              Details ({arr.length} items)
            </div>
            <div className="bg-background/50 rounded max-h-64 overflow-auto">
              {isObjectArray && columns ? (
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-background border-b">
                    <tr>
                      {columns.map(col => (
                        <th key={col} className="text-left p-2 font-medium capitalize whitespace-nowrap">
                          {col.replace(/_/g, " ")}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {arr.map((item, i) => (
                      <tr key={i} className="border-b border-border/20 last:border-0 hover:bg-white/5">
                        {columns.map(col => (
                          <td key={col} className="p-2 font-mono text-muted-foreground">
                            {typeof item[col] === "number"
                              ? (item[col] as number).toLocaleString()
                              : String(item[col] ?? "")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="p-2 space-y-1">
                  {arr.map((item, i) => (
                    <div key={i} className="text-xs font-mono text-muted-foreground py-1 border-b border-border/20 last:border-0">
                      {String(item)}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        );
      })()}
    </div>
  );
}

// Batch result type
export interface BatchResult {
  taskName: string;
  taskId: string;
  status: "success" | "error" | "timeout";
  result: Record<string, unknown> | null;
  error?: string;
}

// Props for batch results dialog
interface BatchResultsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  dryRun: boolean;
  results: BatchResult[];
}

/**
 * Dialog for displaying batch maintenance task results.
 * Shows expandable results for each task with success/error status.
 */
export function BatchResultsDialog({
  open,
  onOpenChange,
  dryRun,
  results,
}: BatchResultsDialogProps) {
  const successCount = results.filter(r => r.status === "success").length;
  const errorCount = results.filter(r => r.status === "error").length;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="!max-w-[90vw] !w-[1400px] !h-[85vh] flex flex-col overflow-hidden">
        <DialogHeader className="flex-shrink-0">
          <DialogTitle className="text-xl">
            {dryRun ? "Maintenance Dry Run Report" : "Maintenance Execution Report"}
          </DialogTitle>
          <DialogDescription>
            {dryRun
              ? "Preview of what would happen. No changes were made."
              : "Summary of executed maintenance tasks."}
            {" • "}{results.length} tasks • {successCount} success • {errorCount} errors
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 min-h-0 overflow-y-auto pr-2">
          <div className="space-y-4 py-4">
            {results.map((result, idx) => (
              <details
                key={idx}
                className={`border rounded-lg ${
                  result.status === "error"
                    ? "border-red-500/50 bg-red-500/5"
                    : result.status === "timeout"
                    ? "border-yellow-500/50 bg-yellow-500/5"
                    : "border-green-500/50 bg-green-500/5"
                }`}
              >
                <summary className="flex items-center gap-2 p-3 cursor-pointer select-none hover:bg-white/5">
                  {result.status === "success" ? (
                    <CheckCircle2 className="h-5 w-5 text-green-500 flex-shrink-0" />
                  ) : result.status === "error" ? (
                    <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
                  ) : (
                    <Loader2 className="h-5 w-5 text-yellow-500 flex-shrink-0" />
                  )}
                  <span className="font-semibold">{result.taskName}</span>
                  <Badge
                    variant={result.status === "success" ? "default" : "destructive"}
                    className={result.status === "success" ? "bg-green-600" : ""}
                  >
                    {result.status}
                  </Badge>
                  {result.error && (
                    <span className="text-red-400 text-xs ml-2 truncate">{result.error.slice(0, 50)}...</span>
                  )}
                </summary>

                <div className="px-4 pb-4">
                  {result.error && (
                    <div className="text-red-400 text-sm mb-2 font-mono">
                      Error: {result.error}
                    </div>
                  )}

                  {result.result && (
                    <TaskResultDisplay result={result.result as Record<string, unknown>} />
                  )}
                </div>
              </details>
            ))}
          </div>
        </div>

        <DialogFooter className="flex-shrink-0 border-t pt-4">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
