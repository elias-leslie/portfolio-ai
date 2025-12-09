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
  const [activeTab, setActiveTab] = useState("all");

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ["workflow-graph"] });
  };

  return (
    <PageContainer>
      <PageHeader
        title="Workflow Visualization"
        description="Task dependencies and execution flow - see how tasks interconnect"
        actions={
          <Button variant="outline" size="sm" onClick={handleRefresh}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        }
      />

      <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-6">
        <TabsList>
          <TabsTrigger value="all">All Tasks</TabsTrigger>
          <TabsTrigger value="data-pipeline">Data Pipeline</TabsTrigger>
          <TabsTrigger value="strategy">Strategy</TabsTrigger>
          <TabsTrigger value="system">System</TabsTrigger>
        </TabsList>

        <TabsContent value="all" className="mt-4">
          {/* Show ALL tasks with ALL dependencies - the unified view */}
          <WorkflowCanvas />
        </TabsContent>

        <TabsContent value="data-pipeline" className="mt-4">
          <WorkflowCanvas category="market_data,news" />
        </TabsContent>

        <TabsContent value="strategy" className="mt-4">
          <WorkflowCanvas category="strategy" />
        </TabsContent>

        <TabsContent value="system" className="mt-4">
          <WorkflowCanvas category="infrastructure,analytics,portfolio" />
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}
