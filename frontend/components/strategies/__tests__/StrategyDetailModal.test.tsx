import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { StrategyDetailModal } from "../StrategyDetailModal";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

// Mock hooks
vi.mock("@/lib/hooks/useStrategies", () => ({
  useStrategy: vi.fn(() => ({
    data: null,
    isLoading: false,
  })),
  useUpdateStrategyStatus: vi.fn(() => ({
    mutate: vi.fn(),
  })),
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  function TestWrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return TestWrapper;
}

describe("StrategyDetailModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state", async () => {
    const { useStrategy } = await import("@/lib/hooks/useStrategies");
    (useStrategy as unknown as vi.Mock).mockReturnValue({
      data: null,
      isLoading: true,
    });

    render(
      <StrategyDetailModal
        strategyId="test-id"
        open={true}
        onOpenChange={() => {}}
      />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByText("Loading Strategy...")).toBeInTheDocument();
  });

  it("does not render content when closed", async () => {
    const { useStrategy } = await import("@/lib/hooks/useStrategies");
    (useStrategy as unknown as vi.Mock).mockReturnValue({
      data: null,
      isLoading: false,
    });

    render(
      <StrategyDetailModal
        strategyId="strategy-1"
        open={false}
        onOpenChange={() => {}}
      />,
      { wrapper: createWrapper() }
    );

    // Content should not be rendered when dialog is closed
    expect(screen.queryByText("Loading Strategy...")).not.toBeInTheDocument();
  });

  it("calls useStrategy with correct strategyId", async () => {
    const { useStrategy } = await import("@/lib/hooks/useStrategies");
    const mockUseStrategy = useStrategy as unknown as vi.Mock;
    mockUseStrategy.mockReturnValue({
      data: null,
      isLoading: false,
    });

    render(
      <StrategyDetailModal
        strategyId="test-strategy-123"
        open={true}
        onOpenChange={() => {}}
      />,
      { wrapper: createWrapper() }
    );

    expect(mockUseStrategy).toHaveBeenCalledWith("test-strategy-123");
  });

  it("calls useStrategy with null when strategyId is null", async () => {
    const { useStrategy } = await import("@/lib/hooks/useStrategies");
    const mockUseStrategy = useStrategy as unknown as vi.Mock;
    mockUseStrategy.mockReturnValue({
      data: null,
      isLoading: false,
    });

    render(
      <StrategyDetailModal
        strategyId={null}
        open={true}
        onOpenChange={() => {}}
      />,
      { wrapper: createWrapper() }
    );

    expect(mockUseStrategy).toHaveBeenCalledWith(null);
  });
});
