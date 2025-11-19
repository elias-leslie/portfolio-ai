import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { AccountsWithPositions } from "../AccountsWithPositions";
import {
  useAccounts,
  usePortfolio,
  useDeleteAccount,
  useDeletePosition,
  useUpdatePosition,
} from "@/lib/hooks/usePortfolio";

vi.mock("@/lib/hooks/usePortfolio", () => ({
  useAccounts: vi.fn(),
  usePortfolio: vi.fn(),
  useDeleteAccount: vi.fn(),
  useDeletePosition: vi.fn(),
  useUpdatePosition: vi.fn(),
}));

const mockUseAccounts = useAccounts as unknown as vi.Mock;
const mockUsePortfolio = usePortfolio as unknown as vi.Mock;
const mockUseDeleteAccount = useDeleteAccount as unknown as vi.Mock;
const mockUseDeletePosition = useDeletePosition as unknown as vi.Mock;
const mockUseUpdatePosition = useUpdatePosition as unknown as vi.Mock;

describe("AccountsWithPositions", () => {
  beforeEach(() => {
    mockUsePortfolio.mockReturnValue({
      data: { positions: [] },
      isLoading: false,
    });
    mockUseDeleteAccount.mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    });
    mockUseDeletePosition.mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    });
    mockUseUpdatePosition.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    });
  });

  it("renders skeleton while accounts or portfolio are loading", () => {
    mockUseAccounts.mockReturnValue({
      data: undefined,
      isLoading: true,
    });
    mockUsePortfolio.mockReturnValue({
      data: undefined,
      isLoading: true,
    });

    render(<AccountsWithPositions />);

    expect(
      screen.getByTestId("accounts-with-positions-skeleton"),
    ).toBeInTheDocument();
  });

  it("shows empty state when no accounts exist", () => {
    mockUseAccounts.mockReturnValue({
      data: [],
      isLoading: false,
    });

    render(<AccountsWithPositions />);

    expect(
      screen.getByText(/No accounts yet\. Click "Add Account"/i),
    ).toBeVisible();
  });
});
