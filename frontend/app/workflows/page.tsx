"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";

import { PageContainer } from "@/components/shared/PageContainer";
import { PageHeader } from "@/components/shared/PageHeader";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { WorkflowCanvas } from "@/components/workflows/WorkflowCanvas";

export default function WorkflowsPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("data-pipeline");

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ["workflow-graph"] });
  };

  return (
    <PageContainer>
      <PageHeader
        title="Workflow Visualization"
        description="Task dependencies and execution flow"
        actions={
          <Button variant="outline" size="sm" onClick={handleRefresh}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        }
      />

      <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-6">
        <TabsList>
          <TabsTrigger value="data-pipeline">Data Pipeline</TabsTrigger>
          <TabsTrigger value="strategy">Trading Strategy</TabsTrigger>
          <TabsTrigger value="system">System Health</TabsTrigger>
          <TabsTrigger value="agents">Multi-Agent</TabsTrigger>
        </TabsList>

        <TabsContent value="data-pipeline" className="mt-4">
          <WorkflowCanvas category="market_data,news" />
        </TabsContent>

        <TabsContent value="strategy" className="mt-4">
          <WorkflowCanvas category="strategy" />
        </TabsContent>

        <TabsContent value="system" className="mt-4">
          <WorkflowCanvas category="infrastructure,analytics" />
        </TabsContent>

        <TabsContent value="agents" className="mt-4">
          <div className="h-[600px] w-full border rounded-lg bg-muted/20 flex items-center justify-center">
            <div className="text-center py-12 text-muted-foreground">
              <p className="font-medium">Multi-agent workflow visualization</p>
              <p className="text-sm mt-1">Coming in Phase 2</p>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}
