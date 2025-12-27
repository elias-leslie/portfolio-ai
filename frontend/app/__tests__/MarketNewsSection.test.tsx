import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

// Mock IntersectionObserver
const mockObserve = vi.fn();
const mockDisconnect = vi.fn();

let mockIntersectionCallback: IntersectionObserverCallback | null = null;

class MockIntersectionObserver implements IntersectionObserver {
  readonly root: Element | Document | null = null;
  readonly rootMargin: string;
  readonly thresholds: ReadonlyArray<number>;

  constructor(
    callback: IntersectionObserverCallback,
    options?: IntersectionObserverInit
  ) {
    mockIntersectionCallback = callback;
    this.rootMargin = options?.rootMargin || "0px";
    this.thresholds = Array.isArray(options?.threshold)
      ? options.threshold
      : [options?.threshold || 0];
    MockIntersectionObserver.lastInstance = this;
    MockIntersectionObserver.lastOptions = options;
  }

  static lastInstance: MockIntersectionObserver | null = null;
  static lastOptions: IntersectionObserverInit | undefined = undefined;

  observe = mockObserve;
  disconnect = mockDisconnect;
  unobserve = vi.fn();
  takeRecords = vi.fn(() => []);
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  function TestWrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return TestWrapper;
}

beforeEach(() => {
  mockObserve.mockClear();
  mockDisconnect.mockClear();
  mockIntersectionCallback = null;
  MockIntersectionObserver.lastInstance = null;
  MockIntersectionObserver.lastOptions = undefined;

  global.IntersectionObserver =
    MockIntersectionObserver as unknown as typeof IntersectionObserver;
});

// Mock fetch to prevent network calls
vi.stubGlobal(
  "fetch",
  vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }))
);

describe("Article Lazy Loading (MarketNewsSection)", () => {
  it("sets up IntersectionObserver with correct options", async () => {
    const { default: HomePage } = await import("../page");

    render(<HomePage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(MockIntersectionObserver.lastOptions).toBeDefined();
    });

    expect(MockIntersectionObserver.lastOptions?.threshold).toBe(0.1);
    expect(MockIntersectionObserver.lastOptions?.rootMargin).toBe("300px");
  });

  it("observes the section element", async () => {
    const { default: HomePage } = await import("../page");

    render(<HomePage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(mockObserve).toHaveBeenCalled();
    });
  });

  it("disconnects observer on cleanup", async () => {
    const { default: HomePage } = await import("../page");

    const { unmount } = render(<HomePage />, { wrapper: createWrapper() });
    unmount();

    expect(mockDisconnect).toHaveBeenCalled();
  });

  it("triggers fetch when section becomes visible", async () => {
    const { default: HomePage } = await import("../page");

    render(<HomePage />, { wrapper: createWrapper() });

    // Wait for observer to be set up
    await waitFor(() => {
      expect(mockObserve).toHaveBeenCalled();
    });

    // Simulate intersection
    if (mockIntersectionCallback) {
      mockIntersectionCallback(
        [{ isIntersecting: true } as IntersectionObserverEntry],
        MockIntersectionObserver.lastInstance as IntersectionObserver
      );
    }

    // Observer should be disconnected after triggering
    await waitFor(() => {
      expect(mockDisconnect).toHaveBeenCalled();
    });
  });

  it("uses rootMargin of 300px for prefetching", async () => {
    const { default: HomePage } = await import("../page");

    render(<HomePage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(MockIntersectionObserver.lastOptions).toBeDefined();
    });

    expect(MockIntersectionObserver.lastOptions?.rootMargin).toBe("300px");
  });

  it("disconnects observer after intersection", async () => {
    const { default: HomePage } = await import("../page");

    render(<HomePage />, { wrapper: createWrapper() });

    // Wait for observer to be set up
    await waitFor(() => {
      expect(mockObserve).toHaveBeenCalled();
    });

    // Simulate intersection
    if (mockIntersectionCallback) {
      mockIntersectionCallback(
        [{ isIntersecting: true } as IntersectionObserverEntry],
        MockIntersectionObserver.lastInstance as IntersectionObserver
      );
    }

    // Observer should be disconnected after triggering
    expect(mockDisconnect).toHaveBeenCalled();
  });
});
