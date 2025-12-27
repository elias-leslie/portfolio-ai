import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProfileSelector } from "../ProfileSelector";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

// Mock hooks
vi.mock("@/lib/hooks/useSettingsProfiles", () => ({
  useProfiles: vi.fn(() => ({
    data: [],
    isLoading: false,
  })),
  useCreateProfile: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useDeleteProfile: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useActivateProfile: vi.fn(() => ({ mutateAsync: vi.fn() })),
  useDuplicateProfile: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useExportProfile: vi.fn(() => ({ mutateAsync: vi.fn() })),
  useImportProfile: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const mockPreferences = {
  id: 1,
  userId: 1,
  emailNotifications: true,
  alertsEnabled: true,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
};

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  function TestWrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return TestWrapper;
}

describe("ProfileSelector", () => {
  const mockOnProfileLoad = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state", async () => {
    const { useProfiles } = await import("@/lib/hooks/useSettingsProfiles");
    (useProfiles as unknown as vi.Mock).mockReturnValue({
      data: [],
      isLoading: true,
    });

    render(
      <ProfileSelector
        currentPreferences={mockPreferences}
        onProfileLoad={mockOnProfileLoad}
      />,
      { wrapper: createWrapper() }
    );

    // Should show loading skeleton
    expect(document.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("renders Settings Profiles label", async () => {
    const { useProfiles } = await import("@/lib/hooks/useSettingsProfiles");
    (useProfiles as unknown as vi.Mock).mockReturnValue({
      data: [],
      isLoading: false,
    });

    render(
      <ProfileSelector
        currentPreferences={mockPreferences}
        onProfileLoad={mockOnProfileLoad}
      />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByText("Settings Profiles")).toBeInTheDocument();
  });

  it("renders Import button", async () => {
    const { useProfiles } = await import("@/lib/hooks/useSettingsProfiles");
    (useProfiles as unknown as vi.Mock).mockReturnValue({
      data: [],
      isLoading: false,
    });

    render(
      <ProfileSelector
        currentPreferences={mockPreferences}
        onProfileLoad={mockOnProfileLoad}
      />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByText("Import")).toBeInTheDocument();
  });

  it("renders Save As button", async () => {
    const { useProfiles } = await import("@/lib/hooks/useSettingsProfiles");
    (useProfiles as unknown as vi.Mock).mockReturnValue({
      data: [],
      isLoading: false,
    });

    render(
      <ProfileSelector
        currentPreferences={mockPreferences}
        onProfileLoad={mockOnProfileLoad}
      />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByText("Save As")).toBeInTheDocument();
  });

  it("renders profile selector dropdown", async () => {
    const { useProfiles } = await import("@/lib/hooks/useSettingsProfiles");
    (useProfiles as unknown as vi.Mock).mockReturnValue({
      data: [],
      isLoading: false,
    });

    render(
      <ProfileSelector
        currentPreferences={mockPreferences}
        onProfileLoad={mockOnProfileLoad}
      />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByText("Select a profile...")).toBeInTheDocument();
  });

  it("renders description text", async () => {
    const { useProfiles } = await import("@/lib/hooks/useSettingsProfiles");
    (useProfiles as unknown as vi.Mock).mockReturnValue({
      data: [],
      isLoading: false,
    });

    render(
      <ProfileSelector
        currentPreferences={mockPreferences}
        onProfileLoad={mockOnProfileLoad}
      />,
      { wrapper: createWrapper() }
    );

    expect(
      screen.getByText(/Save different configurations for various trading strategies/)
    ).toBeInTheDocument();
  });

  it("displays active profile when available", async () => {
    const { useProfiles } = await import("@/lib/hooks/useSettingsProfiles");
    (useProfiles as unknown as vi.Mock).mockReturnValue({
      data: [
        {
          id: 1,
          name: "Conservative Strategy",
          description: "Low risk profile",
          isActive: true,
          profileData: mockPreferences,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
      ],
      isLoading: false,
    });

    render(
      <ProfileSelector
        currentPreferences={mockPreferences}
        onProfileLoad={mockOnProfileLoad}
      />,
      { wrapper: createWrapper() }
    );

    // Profile name appears in both dropdown and active profile card
    const profileNames = screen.getAllByText("Conservative Strategy");
    expect(profileNames.length).toBeGreaterThan(0);
    expect(screen.getByText("Low risk profile")).toBeInTheDocument();
  });
});
