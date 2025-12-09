"use client";

import { useMemo, useCallback, useEffect } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  Position,
} from "@xyflow/react";
import dagre from "dagre";
import "@xyflow/react/dist/style.css";
import "./workflow-canvas.css";

import { useWorkflowGraph } from "@/lib/hooks/useWorkflowGraph";
import { TaskNode } from "./TaskNode";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { WorkflowNode, WorkflowEdge, NodeData } from "@/lib/api/workflows";

// Register custom node types
const nodeTypes = {
  task: TaskNode,
};

const NODE_WIDTH = 180;
const NODE_HEIGHT = 120;

function getLayoutedElements(
  nodes: WorkflowNode[],
  edges: WorkflowEdge[]
): { nodes: Node<NodeData>[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({
    rankdir: "LR",        // Left to right flow
    nodesep: 200,         // Vertical spacing between nodes in same column
    ranksep: 600,         // Horizontal spacing between columns
    marginx: 20,          // Margin on left/right
    marginy: 20,          // Margin on top/bottom
    // ranker: "tight-tree", // Removed to allow better spreading
  });

  nodes.forEach((node) => {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  });

  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target);
  });

  dagre.layout(g);

  const layoutedNodes: Node<NodeData>[] = nodes.map((node) => {
    const nodeWithPosition = g.node(node.id);
    return {
      id: node.id,
      type: "task",
      position: {
        x: nodeWithPosition.x - NODE_WIDTH / 2,
        y: nodeWithPosition.y - NODE_HEIGHT / 2,
      },
      data: node.data,
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    };
  });

  const layoutedEdges: Edge[] = edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: "smoothstep",
    animated: edge.animated || false,
    style: {
      stroke: edge.animated ? "#3b82f6" : "#94a3b8",
      strokeWidth: edge.animated ? 2 : 1,
    },
  }));

  return { nodes: layoutedNodes, edges: layoutedEdges };
}

interface WorkflowCanvasProps {
  category?: string;
  fullHeight?: boolean;
}

export function WorkflowCanvas({ category, fullHeight = false }: WorkflowCanvasProps) {
  const heightClass = fullHeight ? "h-full" : "h-[600px]";
  const { data, isLoading, error, refetch } = useWorkflowGraph(category);

  // Compute layout
  const { layoutedNodes, layoutedEdges } = useMemo(() => {
    if (!data?.nodes || !data?.edges) {
      return { layoutedNodes: [], layoutedEdges: [] };
    }
    const { nodes, edges } = getLayoutedElements(data.nodes, data.edges);
    return { layoutedNodes: nodes, layoutedEdges: edges };
  }, [data]);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node<NodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  // Update nodes/edges when data changes
  useEffect(() => {
    if (layoutedNodes.length > 0) {
      setNodes(layoutedNodes);
      setEdges(layoutedEdges);
    }
  }, [layoutedNodes, layoutedEdges, setNodes, setEdges]);

  const onRefresh = useCallback(() => {
    refetch();
  }, [refetch]);

  if (isLoading) {
    return (
      <div className={`${heightClass} w-full border rounded-lg bg-muted/20 flex items-center justify-center`}>
        <div className="flex flex-col items-center gap-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-32" />
          <div className="flex gap-4 mt-4">
            <Skeleton className="h-24 w-44 rounded-lg" />
            <Skeleton className="h-24 w-44 rounded-lg" />
            <Skeleton className="h-24 w-44 rounded-lg" />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`${heightClass} w-full border rounded-lg bg-muted/20 flex items-center justify-center`}>
        <div className="flex flex-col items-center gap-4 text-center">
          <AlertCircle className="h-12 w-12 text-destructive" />
          <div>
            <p className="font-medium">Failed to load workflow graph</p>
            <p className="text-sm text-muted-foreground mt-1">
              {error instanceof Error ? error.message : "Unknown error"}
            </p>
          </div>
          <Button variant="outline" onClick={onRefresh}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </div>
      </div>
    );
  }

  if (!data?.nodes || data.nodes.length === 0) {
    return (
      <div className={`${heightClass} w-full border rounded-lg bg-muted/20 flex items-center justify-center`}>
        <div className="text-center">
          <p className="text-muted-foreground">No tasks found</p>
          <p className="text-sm text-muted-foreground mt-1">
            Check if tasks are configured in the system
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={`${heightClass} w-full border rounded-lg overflow-hidden`}>
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: fullHeight ? 0.05 : 0.2, minZoom: 0.2, maxZoom: 1.5 }}
          proOptions={{ hideAttribution: true }}
          minZoom={0.1}
          maxZoom={2}
        >
          <Background gap={20} size={1} />
          <Controls />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}
