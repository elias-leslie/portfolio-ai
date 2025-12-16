/**
 * Files Tab - Explorer with Inline Details
 *
 * Unified file explorer with:
 * - Tree/table hybrid view (folders expand to show files)
 * - Sortable columns (Name, Files, LOC, Size)
 * - Color indicators for bloat (left border + colored text)
 * - Inline details expansion (click row to show details below)
 * - Chevron click expands children, row click expands details
 */

"use client";

import { useState, useCallback, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Folder,
  FolderOpen,
  File,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Search,
  Loader2,
  Home,
  ChevronRightIcon,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  X,
  GitCommit as GitCommitIcon,
  Copy,
  CheckSquare,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

// Types
interface FileSummary {
  totalFiles: number;
  totalDirectories: number;
  totalLoc: number;
  bloatWarnings: number;
  bloatCritical: number;
  staleFiles: number;
  orphanFiles: number;
  freshFiles: number;
  untrackedFiles: number;
  lastScan: string | null;
  byExtension: Array<{ extension: string; count: number; loc: number }>;
}

interface FileNode {
  path: string;
  name: string;
  isDirectory: boolean;
  extension: string | null;
  sizeBytes: number;
  linesOfCode: number;
  fileCount: number | null;
  totalLoc: number | null;
  bloatLevel: "warning" | "critical" | null;
  lastModified: string | null;
  subdirCount: number;
  directFileCount: number;
  hasChildren: boolean;
  // Stale detection fields
  lastCommitDays: number | null;
  referenceCount: number | null;
  staleStatus: "fresh" | "stale" | "orphan" | "untracked" | null;
}

type SortField = "name" | "loc" | "size" | "files" | "modified";
type SortDir = "asc" | "desc";

// API functions
async function fetchSummary(): Promise<FileSummary> {
  const res = await fetch("/api/files/summary");
  if (!res.ok) throw new Error("Failed to fetch file summary");
  return res.json();
}

async function fetchChildren(
  path: string,
  sort: SortField,
  dir: SortDir,
  foldersFirst: boolean
): Promise<FileNode[]> {
  const params = new URLSearchParams({
    path,
    sort,
    dir,
    foldersFirst: String(foldersFirst),
    includeFiles: "true",
  });
  const res = await fetch(`/api/files/children?${params}`);
  if (!res.ok) throw new Error("Failed to fetch children");
  return res.json();
}

async function triggerScan(): Promise<{ status: string; message: string }> {
  const res = await fetch("/api/files/scan", { method: "POST" });
  if (!res.ok) throw new Error("Failed to trigger scan");
  return res.json();
}

interface GitCommit {
  hash: string;
  fullHash: string;
  author: string;
  date: string;
  subject: string;
  linesAdded: number;
  linesDeleted: number;
}

interface GitHistory {
  commits: GitCommit[];
  totalCommits: number;
  filePath: string;
  error?: string;
}

async function fetchGitHistory(path: string): Promise<GitHistory> {
  const res = await fetch(`/api/files/history?path=${encodeURIComponent(path)}&limit=5`);
  if (!res.ok) return { commits: [], totalCommits: 0, filePath: path, error: "Failed to fetch" };
  return res.json();
}

interface FilesListResponse {
  items: FileNode[];
  total: number;
  limit: number;
  offset: number;
}

async function fetchAllFiles(
  sort: SortField,
  dir: SortDir
): Promise<FilesListResponse> {
  const sortMap: Record<SortField, string> = {
    name: "path",
    loc: "lines_of_code",
    size: "size_bytes",
    files: "path",
    modified: "last_modified",
  };
  const params = new URLSearchParams({
    isDirectory: "false",
    sort: sortMap[sort],
    dir,
    limit: "500",
    offset: "0",
  });
  const res = await fetch(`/api/files?${params}`);
  if (!res.ok) throw new Error("Failed to fetch files");
  const data = await res.json();
  // Transform to match FileNode interface
  return {
    ...data,
    items: data.items.map((item: Record<string, unknown>) => ({
      ...item,
      name: (item.path as string).split("/").pop() || item.path,
      subdirCount: 0,
      directFileCount: 0,
      hasChildren: false,
    })),
  };
}

// Helper functions
const formatNumber = (n: number) => n.toLocaleString();
const formatBytes = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const formatDate = (dateStr: string | null) => {
  if (!dateStr) return "-";
  const date = new Date(dateStr);
  return date.toLocaleDateString();
};

// Inline Details Component
function InlineDetails({
  node,
  onClose,
  depth,
}: {
  node: FileNode;
  onClose: () => void;
  depth: number;
}) {
  const isDir = node.isDirectory;
  const loc = isDir ? node.totalLoc || 0 : node.linesOfCode;
  const bloatStatus = node.bloatLevel;
  const staleStatus = node.staleStatus;

  // Fetch git history for files only
  const { data: gitHistory, isLoading: historyLoading } = useQuery({
    queryKey: ["files", "history", node.path],
    queryFn: () => fetchGitHistory(node.path),
    enabled: !isDir,
    staleTime: 60000, // Cache for 1 minute
  });

  return (
    <div
      className={cn(
        "mx-2 mb-1 rounded border bg-surface-alt",
        bloatStatus === "critical" && "border-loss/30 bg-loss/5",
        bloatStatus === "warning" && "border-warning/30 bg-warning/5",
        staleStatus === "orphan" && !bloatStatus && "border-loss/30 bg-loss/5",
        staleStatus === "stale" && !bloatStatus && "border-accent/30 bg-accent/5",
        staleStatus === "untracked" && !bloatStatus && "border-neutral/30 bg-neutral/5",
        !bloatStatus && (!staleStatus || staleStatus === "fresh") && "border-border"
      )}
      style={{ marginLeft: depth * 20 + 8 }}
    >
      <div className="p-3">
        {/* Header row */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2">
            {isDir ? (
              <Folder className="h-4 w-4 text-primary" />
            ) : (
              <File className="h-4 w-4 text-text-secondary" />
            )}
            <span className="font-medium text-sm">{node.name}</span>
            {bloatStatus && (
              <Badge
                variant={bloatStatus === "critical" ? "destructive" : "outline"}
                className={cn(
                  "text-xs",
                  bloatStatus === "warning" && "border-warning text-warning"
                )}
              >
                {bloatStatus}
              </Badge>
            )}
            {staleStatus && staleStatus !== "fresh" && (
              <Badge
                variant={staleStatus === "orphan" ? "destructive" : "outline"}
                className={cn(
                  "text-xs",
                  staleStatus === "stale" && "border-accent text-accent",
                  staleStatus === "untracked" && "border-neutral text-neutral"
                )}
              >
                {staleStatus}
              </Badge>
            )}
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-5 w-5 -mr-1 -mt-1"
            onClick={(e) => {
              e.stopPropagation();
              onClose();
            }}
          >
            <X className="h-3 w-3" />
          </Button>
        </div>

        {/* Path */}
        <div className="text-xs text-text-secondary font-mono mb-3 break-all">
          {node.path}
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-4 gap-2 text-xs">
          <div className="bg-background/50 rounded px-2 py-1.5">
            <div className="text-text-secondary">{isDir ? "Total LOC" : "Lines"}</div>
            <div className="font-semibold">{formatNumber(loc)}</div>
          </div>
          <div className="bg-background/50 rounded px-2 py-1.5">
            <div className="text-text-secondary">{isDir ? "Files" : "Size"}</div>
            <div className="font-semibold">
              {isDir ? node.fileCount : formatBytes(node.sizeBytes)}
            </div>
          </div>
          {isDir ? (
            <>
              <div className="bg-background/50 rounded px-2 py-1.5">
                <div className="text-text-secondary">Subdirs</div>
                <div className="font-semibold">{node.subdirCount}</div>
              </div>
              <div className="bg-background/50 rounded px-2 py-1.5">
                <div className="text-text-secondary">Direct</div>
                <div className="font-semibold">{node.directFileCount}</div>
              </div>
            </>
          ) : (
            <>
              <div className="bg-background/50 rounded px-2 py-1.5">
                <div className="text-text-secondary">Type</div>
                <div className="font-semibold">{node.extension || "-"}</div>
              </div>
              <div className="bg-background/50 rounded px-2 py-1.5">
                <div className="text-text-secondary">Modified</div>
                <div className="font-semibold">{formatDate(node.lastModified)}</div>
              </div>
            </>
          )}
        </div>

        {/* Stale info row - only show for files with stale data */}
        {!isDir && (node.lastCommitDays !== null || node.referenceCount !== null) && (
          <div className="grid grid-cols-2 gap-2 text-xs mt-2">
            <div className="bg-background/50 rounded px-2 py-1.5">
              <div className="text-text-secondary">Last Commit</div>
              <div className={cn(
                "font-semibold",
                node.lastCommitDays !== null && node.lastCommitDays >= 90 && "text-accent"
              )}>
                {node.lastCommitDays !== null ? `${node.lastCommitDays} days ago` : "-"}
              </div>
            </div>
            <div className="bg-background/50 rounded px-2 py-1.5">
              <div className="text-text-secondary">References</div>
              <div className={cn(
                "font-semibold",
                node.referenceCount === 0 && "text-accent"
              )}>
                {node.referenceCount ?? "-"}
              </div>
            </div>
          </div>
        )}

        {/* Git History section - for files only */}
        {!isDir && (
          <div className="mt-3 pt-2 border-t border-border/50">
            <div className="flex items-center gap-2 mb-2">
              <GitCommitIcon className="h-3.5 w-3.5 text-text-secondary" />
              <span className="text-xs font-medium text-text-secondary">
                Recent Commits
                {gitHistory?.totalCommits ? ` (${gitHistory.totalCommits} total)` : ""}
              </span>
            </div>
            {historyLoading ? (
              <div className="flex items-center gap-2 text-xs text-text-secondary">
                <Loader2 className="h-3 w-3 animate-spin" />
                <span>Loading history...</span>
              </div>
            ) : gitHistory?.error ? (
              <div className="text-xs text-text-secondary italic">{gitHistory.error}</div>
            ) : gitHistory?.commits.length === 0 ? (
              <div className="text-xs text-text-secondary italic">No git history found</div>
            ) : (
              <div className="space-y-1.5">
                {gitHistory?.commits.slice(0, 3).map((commit) => (
                  <div
                    key={commit.fullHash}
                    className="flex items-start gap-2 text-xs bg-background/50 rounded px-2 py-1.5"
                  >
                    <span className="font-mono text-primary/70 flex-shrink-0">{commit.hash}</span>
                    <div className="flex-1 min-w-0">
                      <div className="truncate" title={commit.subject}>{commit.subject}</div>
                      <div className="text-text-secondary">
                        {commit.author} · {new Date(commit.date).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Status message */}
        {bloatStatus && (
          <div className="mt-2 text-xs text-text-secondary">
            {isDir
              ? `Contains ${node.fileCount} files (threshold: 50 for warning, 50+ for critical)`
              : `${formatNumber(loc)} lines exceeds ${node.extension === ".py" ? "500/1000" : "300/600"} LOC threshold`}
          </div>
        )}

        {/* Suggestion */}
        {bloatStatus === "critical" && !isDir && (
          <div className="mt-2 pt-2 border-t border-border/50 text-xs">
            <span className="text-text-secondary">Suggestion: </span>
            <span>Consider splitting this file into smaller modules</span>
          </div>
        )}
      </div>
    </div>
  );
}

// Main Component
export function FilesTab() {
  const queryClient = useQueryClient();

  // State
  const [sortField, setSortField] = useState<SortField>("name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [foldersFirst, setFoldersFirst] = useState(true);
  const [filesOnly, setFilesOnly] = useState(false);
  const [filesOnlyAutoSet, setFilesOnlyAutoSet] = useState(false); // Track if auto-set by bloat filter
  const [searchFilter, setSearchFilter] = useState("");
  const [bloatFilter, setBloatFilter] = useState<"all" | "warning" | "critical">("all");
  const [staleFilter, setStaleFilter] = useState<"all" | "stale" | "orphan" | "untracked">("all");
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set()); // Children expanded
  const [detailsOpenPaths, setDetailsOpenPaths] = useState<Set<string>>(new Set()); // Details expanded
  const [loadedChildren, setLoadedChildren] = useState<Map<string, FileNode[]>>(
    new Map()
  );
  const [loadingPaths, setLoadingPaths] = useState<Set<string>>(new Set());
  const [currentPath, setCurrentPath] = useState<string[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set()); // Selected files for review

  // Selection handlers
  const toggleFileSelection = useCallback((path: string, isDir: boolean) => {
    if (isDir) return; // Don't select directories
    setSelectedFiles((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedFiles(new Set());
  }, []);

  const copySelectionToClipboard = useCallback(() => {
    const paths = Array.from(selectedFiles).sort().join("\n");
    navigator.clipboard.writeText(paths);
    toast.success(`${selectedFiles.size} file paths copied to clipboard`);
  }, [selectedFiles]);

  // Queries
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["files", "summary"],
    queryFn: fetchSummary,
  });

  const rootPath = currentPath.join("/");
  const { data: rootChildren, isLoading: rootLoading } = useQuery({
    queryKey: ["files", "children", rootPath, sortField, sortDir, foldersFirst],
    queryFn: () => fetchChildren(rootPath, sortField, sortDir, foldersFirst),
    enabled: !filesOnly,
  });

  // Files-only mode query
  const { data: allFilesData, isLoading: allFilesLoading } = useQuery({
    queryKey: ["files", "all-files", sortField, sortDir],
    queryFn: () => fetchAllFiles(sortField, sortDir),
    enabled: filesOnly,
  });

  // Mutations
  const scanMutation = useMutation({
    mutationFn: triggerScan,
    onSuccess: () => {
      toast.success("File scan started");
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["files"] });
        setLoadedChildren(new Map());
        setExpandedPaths(new Set());
        setDetailsOpenPaths(new Set());
      }, 5000);
    },
    onError: () => toast.error("Failed to start scan"),
  });

  // Handlers
  const loadChildren = useCallback(
    async (path: string) => {
      if (loadedChildren.has(path)) return;
      setLoadingPaths((prev) => new Set(prev).add(path));
      try {
        const children = await fetchChildren(path, sortField, sortDir, foldersFirst);
        setLoadedChildren((prev) => new Map(prev).set(path, children));
      } finally {
        setLoadingPaths((prev) => {
          const next = new Set(prev);
          next.delete(path);
          return next;
        });
      }
    },
    [sortField, sortDir, foldersFirst, loadedChildren]
  );

  // Toggle children expansion (chevron click)
  const toggleChildren = useCallback(
    async (node: FileNode) => {
      if (!node.hasChildren) return;

      const isExpanded = expandedPaths.has(node.path);
      if (isExpanded) {
        setExpandedPaths((prev) => {
          const next = new Set(prev);
          next.delete(node.path);
          return next;
        });
      } else {
        if (!loadedChildren.has(node.path)) {
          await loadChildren(node.path);
        }
        setExpandedPaths((prev) => new Set(prev).add(node.path));
      }
    },
    [expandedPaths, loadedChildren, loadChildren]
  );

  // Toggle details expansion (row click)
  const toggleDetails = useCallback((path: string) => {
    setDetailsOpenPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  const handleSort = useCallback(
    (field: SortField) => {
      if (sortField === field) {
        setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
      } else {
        setSortField(field);
        setSortDir(field === "name" ? "asc" : "desc");
      }
      setLoadedChildren(new Map());
    },
    [sortField]
  );

  const navigateTo = useCallback((pathParts: string[]) => {
    setCurrentPath(pathParts);
    setExpandedPaths(new Set());
    setLoadedChildren(new Map());
    setDetailsOpenPaths(new Set());
  }, []);

  // Filter nodes
  const filteredChildren = useMemo(() => {
    const sourceData = filesOnly ? allFilesData?.items : rootChildren;
    if (!sourceData) return [];

    return sourceData.filter((node) => {
      // Search filter
      if (searchFilter) {
        const lower = searchFilter.toLowerCase();
        if (!node.name.toLowerCase().includes(lower) &&
            !node.path.toLowerCase().includes(lower)) {
          return false;
        }
      }

      // Bloat filter
      if (bloatFilter !== "all") {
        if (bloatFilter === "warning" && node.bloatLevel !== "warning") return false;
        if (bloatFilter === "critical" && node.bloatLevel !== "critical") return false;
      }

      // Stale filter
      if (staleFilter !== "all") {
        if (staleFilter === "stale" && node.staleStatus !== "stale") return false;
        if (staleFilter === "orphan" && node.staleStatus !== "orphan") return false;
        if (staleFilter === "untracked" && node.staleStatus !== "untracked") return false;
      }

      return true;
    });
  }, [rootChildren, allFilesData, filesOnly, searchFilter, bloatFilter, staleFilter]);

  const isLoading = filesOnly ? allFilesLoading : rootLoading;

  // Sort icon
  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <ArrowUpDown className="h-3 w-3 opacity-50" />;
    return sortDir === "asc" ? (
      <ArrowUp className="h-3 w-3" />
    ) : (
      <ArrowDown className="h-3 w-3" />
    );
  };

  // Render tree row
  const renderRow = (node: FileNode, depth: number = 0): React.ReactNode => {
    const isChildrenExpanded = expandedPaths.has(node.path);
    const isDetailsOpen = detailsOpenPaths.has(node.path);
    const isLoading = loadingPaths.has(node.path);
    const children = loadedChildren.get(node.path) || [];
    const loc = node.isDirectory ? node.totalLoc || 0 : node.linesOfCode;

    return (
      <div key={node.path}>
        {/* Main row */}
        <div
          className={cn(
            "flex items-center gap-1 py-1.5 px-2 cursor-pointer transition-colors group",
            "hover:bg-surface-alt",
            isDetailsOpen && "bg-primary/5",
            // Bloat indicator - left border (higher priority)
            node.bloatLevel === "critical" && "border-l-2 border-l-loss",
            node.bloatLevel === "warning" && "border-l-2 border-l-warning",
            // Stale indicator - left border (when no bloat)
            !node.bloatLevel && node.staleStatus === "orphan" && "border-l-2 border-l-loss",
            !node.bloatLevel && node.staleStatus === "stale" && "border-l-2 border-l-accent",
            !node.bloatLevel && node.staleStatus === "untracked" && "border-l-2 border-l-neutral",
            !node.bloatLevel && (!node.staleStatus || node.staleStatus === "fresh") && "border-l-2 border-l-transparent"
          )}
          onClick={() => toggleDetails(node.path)}
        >
          {/* Indentation */}
          <div style={{ width: depth * 20 }} className="flex-shrink-0" />

          {/* Expand/collapse children (chevron) */}
          <div
            className={cn(
              "w-5 h-5 flex items-center justify-center flex-shrink-0 rounded",
              node.hasChildren && "hover:bg-surface-alt"
            )}
            onClick={(e) => {
              e.stopPropagation();
              if (node.hasChildren) toggleChildren(node);
            }}
          >
            {node.hasChildren ? (
              isLoading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-text-secondary" />
              ) : isChildrenExpanded ? (
                <ChevronDown className="h-3.5 w-3.5 text-text-secondary group-hover:text-text-primary" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-text-secondary group-hover:text-text-primary" />
              )
            ) : null}
          </div>

          {/* Selection checkbox (files only) */}
          {!node.isDirectory && (
            <div
              className="w-5 h-5 flex items-center justify-center flex-shrink-0"
              onClick={(e) => {
                e.stopPropagation();
                toggleFileSelection(node.path, node.isDirectory);
              }}
            >
              <Checkbox
                checked={selectedFiles.has(node.path)}
                className="h-3.5 w-3.5"
              />
            </div>
          )}
          {node.isDirectory && <div className="w-5 flex-shrink-0" />}

          {/* Icon */}
          <div className="w-5 flex-shrink-0">
            {node.isDirectory ? (
              isChildrenExpanded ? (
                <FolderOpen
                  className={cn(
                    "h-4 w-4",
                    node.bloatLevel === "critical"
                      ? "text-loss"
                      : node.bloatLevel === "warning"
                        ? "text-warning"
                        : "text-primary"
                  )}
                />
              ) : (
                <Folder
                  className={cn(
                    "h-4 w-4",
                    node.bloatLevel === "critical"
                      ? "text-loss"
                      : node.bloatLevel === "warning"
                        ? "text-warning"
                        : "text-text-secondary"
                  )}
                />
              )
            ) : (
              <File
                className={cn(
                  "h-4 w-4",
                  node.bloatLevel === "critical"
                    ? "text-loss"
                    : node.bloatLevel === "warning"
                      ? "text-warning"
                      : node.staleStatus === "orphan"
                        ? "text-loss"
                        : node.staleStatus === "stale"
                          ? "text-accent"
                          : node.staleStatus === "untracked"
                            ? "text-neutral"
                            : "text-text-secondary"
                )}
              />
            )}
          </div>

          {/* Name */}
          <span
            className={cn(
              "flex-1 truncate text-sm",
              node.bloatLevel === "critical" && "text-loss",
              node.bloatLevel === "warning" && "text-warning",
              !node.bloatLevel && node.staleStatus === "orphan" && "text-loss",
              !node.bloatLevel && node.staleStatus === "stale" && "text-accent",
              !node.bloatLevel && node.staleStatus === "untracked" && "text-neutral",
              !node.bloatLevel && (!node.staleStatus || node.staleStatus === "fresh") && node.isDirectory && "text-primary"
            )}
            title={node.path}
          >
            {filesOnly ? node.path : node.name}
          </span>

          {/* Files column (folders only, hidden in files-only mode) */}
          {!filesOnly && (
            <span className="w-16 text-right text-xs tabular-nums text-primary/70">
              {node.isDirectory ? node.fileCount : ""}
            </span>
          )}

          {/* LOC column */}
          <span className="w-20 text-right text-xs tabular-nums font-mono text-accent/80">
            {formatNumber(loc)}
          </span>

          {/* Size column */}
          <span className="w-16 text-right text-xs tabular-nums text-gain/70">
            {node.isDirectory
              ? (node.sizeBytes ? formatBytes(node.sizeBytes) : "")
              : formatBytes(node.sizeBytes)}
          </span>

          {/* Modified column */}
          <span className="w-20 text-right text-xs tabular-nums text-neutral">
            {node.lastModified
              ? new Date(node.lastModified).toLocaleDateString("en-US", {
                  month: "numeric",
                  day: "numeric",
                  year: "2-digit",
                })
              : ""}
          </span>
        </div>

        {/* Inline details (if open) */}
        {isDetailsOpen && (
          <InlineDetails
            node={node}
            depth={depth}
            onClose={() => toggleDetails(node.path)}
          />
        )}

        {/* Children (if expanded) */}
        {isChildrenExpanded && children.length > 0 && (
          <div>{children.map((child) => renderRow(child, depth + 1))}</div>
        )}
      </div>
    );
  };

  if (summaryLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-text-secondary" />
      </div>
    );
  }

  // Extension colors for visual distinction
  const extColors: Record<string, string> = {
    ".md": "border-primary/50 text-primary",
    ".sql": "border-accent/50 text-accent",
    ".py": "border-gain/50 text-gain",
    ".ts": "border-primary/50 text-primary",
    ".tsx": "border-primary/50 text-primary",
    ".js": "border-warning/50 text-warning",
    ".json": "border-neutral/50 text-neutral",
    ".css": "border-accent/50 text-accent",
  };

  return (
    <div className="flex flex-col h-full">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3 mb-4">
        <div className="bg-surface border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary">Files</div>
          <div className="text-xl font-semibold">
            {formatNumber(summary?.totalFiles || 0)}
          </div>
        </div>
        <div className="bg-surface border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary">Directories</div>
          <div className="text-xl font-semibold">
            {formatNumber(summary?.totalDirectories || 0)}
          </div>
        </div>
        <div className="bg-surface border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary">Total LOC</div>
          <div className="text-xl font-semibold">
            {formatNumber(summary?.totalLoc || 0)}
          </div>
        </div>
        <div className="bg-surface border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary">Warnings</div>
          <div className="text-xl font-semibold text-warning">
            {formatNumber(summary?.bloatWarnings || 0)}
          </div>
        </div>
        <div className="bg-surface border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary">Critical</div>
          <div className="text-xl font-semibold text-loss">
            {formatNumber(summary?.bloatCritical || 0)}
          </div>
        </div>
        <div className="bg-surface border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary">Stale</div>
          <div className="text-xl font-semibold text-accent">
            {formatNumber(summary?.staleFiles || 0)}
          </div>
        </div>
        <div className="bg-surface border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary">Orphan</div>
          <div className="text-xl font-semibold text-loss">
            {formatNumber(summary?.orphanFiles || 0)}
          </div>
        </div>
        <div className="bg-surface border border-border rounded-lg p-3">
          <div className="text-xs text-text-secondary">Untracked</div>
          <div className="text-xl font-semibold text-neutral">
            {formatNumber(summary?.untrackedFiles || 0)}
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3 mb-3">
        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-text-secondary" />
          <Input
            placeholder="Filter..."
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            className="pl-8 h-8"
          />
        </div>

        {/* Folders first toggle */}
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <Checkbox
            checked={foldersFirst}
            onCheckedChange={(checked) => {
              setFoldersFirst(!!checked);
              setLoadedChildren(new Map());
            }}
            disabled={filesOnly}
          />
          <span className={cn("text-text-secondary", filesOnly && "opacity-50")}>
            Folders first
          </span>
        </label>

        {/* Files only toggle */}
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <Checkbox
            checked={filesOnly}
            onCheckedChange={(checked) => {
              setFilesOnly(!!checked);
              setFilesOnlyAutoSet(false); // Manual toggle clears auto-set
              setExpandedPaths(new Set());
              setDetailsOpenPaths(new Set());
            }}
          />
          <span className="text-text-secondary">Files only</span>
        </label>

        {/* Bloat filter */}
        <Select
          value={bloatFilter}
          onValueChange={(v) => {
            const val = v as "all" | "warning" | "critical";
            setBloatFilter(val);
            if (val !== "all" && !filesOnly) {
              setFilesOnly(true);
              setFilesOnlyAutoSet(true);
              setExpandedPaths(new Set());
              setDetailsOpenPaths(new Set());
            } else if (val === "all" && filesOnlyAutoSet) {
              setFilesOnly(false);
              setFilesOnlyAutoSet(false);
            }
          }}
        >
          <SelectTrigger className="w-28 h-8">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="warning">Warning</SelectItem>
            <SelectItem value="critical">Critical</SelectItem>
          </SelectContent>
        </Select>

        {/* Stale filter */}
        <Select
          value={staleFilter}
          onValueChange={(v) => {
            const val = v as "all" | "stale" | "orphan" | "untracked";
            setStaleFilter(val);
            if (val !== "all" && !filesOnly) {
              setFilesOnly(true);
              setFilesOnlyAutoSet(true);
              setExpandedPaths(new Set());
              setDetailsOpenPaths(new Set());
            } else if (val === "all" && filesOnlyAutoSet && bloatFilter === "all") {
              setFilesOnly(false);
              setFilesOnlyAutoSet(false);
            }
          }}
        >
          <SelectTrigger className="w-32 h-8">
            <SelectValue placeholder="Stale" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="stale">Stale</SelectItem>
            <SelectItem value="orphan">Orphan</SelectItem>
            <SelectItem value="untracked">Untracked</SelectItem>
          </SelectContent>
        </Select>

        <div className="flex-1" />

        {/* Selection indicator and actions */}
        {selectedFiles.size > 0 && (
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="flex items-center gap-1">
              <CheckSquare className="h-3 w-3" />
              {selectedFiles.size} selected
            </Badge>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2"
              onClick={copySelectionToClipboard}
              title="Copy file paths"
            >
              <Copy className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2"
              onClick={clearSelection}
              title="Clear selection"
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}

        {/* Scan button */}
        <Button
          variant="outline"
          size="sm"
          onClick={() => scanMutation.mutate()}
          disabled={scanMutation.isPending}
        >
          {scanMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          <span className="ml-1">Scan</span>
        </Button>
      </div>

      {/* Breadcrumb */}
      {currentPath.length > 0 && (
        <div className="flex items-center gap-1 text-sm mb-2">
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2"
            onClick={() => navigateTo([])}
          >
            <Home className="h-3 w-3" />
          </Button>
          {currentPath.map((part, idx) => (
            <div key={idx} className="flex items-center gap-1">
              <ChevronRightIcon className="h-3 w-3 text-text-secondary" />
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2"
                onClick={() => navigateTo(currentPath.slice(0, idx + 1))}
              >
                {part}
              </Button>
            </div>
          ))}
        </div>
      )}

      {/* Explorer - max height to ensure footer is visible */}
      <div className="bg-surface border border-border rounded-lg overflow-hidden flex flex-col" style={{ maxHeight: "calc(100vh - 460px)" }}>
        {/* Column headers */}
        <div className="flex items-center gap-1 px-2 py-2 border-b border-border bg-surface-alt text-xs font-medium text-text-secondary">
          <div style={{ width: 20 }} className="flex-shrink-0" />
          <div className="w-5 flex-shrink-0" />
          <div className="w-5 flex-shrink-0" />
          <button
            className="flex-1 flex items-center gap-1 hover:text-text-primary text-left"
            onClick={() => handleSort("name")}
          >
            Name <SortIcon field="name" />
          </button>
          {!filesOnly && (
            <button
              className="w-16 flex items-center justify-end gap-1 hover:text-text-primary"
              onClick={() => handleSort("files")}
            >
              Files <SortIcon field="files" />
            </button>
          )}
          <button
            className="w-20 flex items-center justify-end gap-1 hover:text-text-primary"
            onClick={() => handleSort("loc")}
          >
            LOC <SortIcon field="loc" />
          </button>
          <button
            className="w-16 flex items-center justify-end gap-1 hover:text-text-primary"
            onClick={() => handleSort("size")}
          >
            Size <SortIcon field="size" />
          </button>
          <button
            className="w-20 flex items-center justify-end gap-1 hover:text-text-primary"
            onClick={() => handleSort("modified")}
          >
            Modified <SortIcon field="modified" />
          </button>
        </div>

        {/* Tree content */}
        <div className="flex-1 overflow-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-text-secondary" />
            </div>
          ) : filteredChildren.length === 0 ? (
            <div className="text-center text-text-secondary py-8">
              {searchFilter
                ? "No matches found"
                : "No files found. Run a scan to populate data."}
            </div>
          ) : (
            <div className="py-1">
              {filteredChildren.map((node) => renderRow(node, 0))}
            </div>
          )}
        </div>

        {/* Footer */}
        {summary?.lastScan && (
          <div className="px-3 py-1.5 border-t border-border text-xs text-text-secondary">
            Last scan: {new Date(summary.lastScan).toLocaleString()}
          </div>
        )}
      </div>

      {/* Extension breakdown */}
      {summary?.byExtension && summary.byExtension.length > 0 && (
        <div className="mt-3 bg-surface border border-border rounded-lg p-3 flex-shrink-0">
          <h3 className="text-xs font-medium text-text-secondary mb-2">
            Lines of Code by Type
          </h3>
          <div className="flex flex-wrap gap-2">
            {summary.byExtension.slice(0, 8).map((ext) => (
              <Badge
                key={ext.extension}
                variant="outline"
                className={cn("text-xs", extColors[ext.extension] || "border-border")}
              >
                {ext.extension}: {formatNumber(ext.loc)} ({ext.count})
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
