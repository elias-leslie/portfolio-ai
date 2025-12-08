import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TradeDistributionChart } from "../TradeDistributionChart";

// Mock recharts to avoid ResizeObserver issues in tests
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  BarChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="bar-chart">{children}</div>
  ),
  Bar: () => <div data-testid="bar" />,
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  CartesianGrid: () => <div data-testid="cartesian-grid" />,
  Cell: () => <div data-testid="cell" />,
  ReferenceLine: () => <div data-testid="reference-line" />,
  Tooltip: () => <div data-testid="tooltip" />,
}));

describe("TradeDistributionChart", () => {
  it("returns null for empty trades array", () => {
    const { container } = render(
      <TradeDistributionChart trades={[]} profitFactor={null} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("returns null for undefined trades", () => {
    const { container } = render(
      <TradeDistributionChart
        trades={undefined as unknown as []}
        profitFactor={null}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders chart with valid trades", () => {
    const trades = [
      { pnl_pct: 5.5 },
      { pnl_pct: -3.2 },
      { pnl_pct: 8.1 },
      { pnl_pct: -1.5 },
    ];

    render(<TradeDistributionChart trades={trades} profitFactor={1.8} />);

    expect(screen.getByText("Trade Distribution")).toBeInTheDocument();
  });

  it("displays key metrics cards", () => {
    const trades = [
      { pnl_pct: 5.0 },
      { pnl_pct: 10.0 },
      { pnl_pct: -3.0 },
      { pnl_pct: -5.0 },
    ];

    render(<TradeDistributionChart trades={trades} profitFactor={1.5} />);

    expect(screen.getByText("Avg Win")).toBeInTheDocument();
    expect(screen.getByText("Avg Loss")).toBeInTheDocument();
    expect(screen.getByText("Profit Factor")).toBeInTheDocument();
    expect(screen.getByText("Win/Loss")).toBeInTheDocument();
  });

  it("calculates correct average win", () => {
    const trades = [
      { pnl_pct: 10.0 },
      { pnl_pct: 20.0 },
      { pnl_pct: -5.0 },
    ];

    render(<TradeDistributionChart trades={trades} profitFactor={null} />);

    // Average win = (10 + 20) / 2 = 15.00%
    expect(screen.getByText("+15.00%")).toBeInTheDocument();
  });

  it("calculates correct average loss", () => {
    const trades = [
      { pnl_pct: 10.0 },
      { pnl_pct: -4.0 },
      { pnl_pct: -6.0 },
    ];

    render(<TradeDistributionChart trades={trades} profitFactor={null} />);

    // Average loss = (-4 + -6) / 2 = -5.00%
    expect(screen.getByText("-5.00%")).toBeInTheDocument();
  });

  it("displays profit factor when provided", () => {
    const trades = [{ pnl_pct: 5.0 }];

    render(<TradeDistributionChart trades={trades} profitFactor={2.35} />);

    expect(screen.getByText("2.35")).toBeInTheDocument();
  });

  it("displays dash for null profit factor", () => {
    const trades = [{ pnl_pct: 5.0 }];

    render(<TradeDistributionChart trades={trades} profitFactor={null} />);

    // Check for dash in the Profit Factor card
    const profitFactorCard = screen
      .getByText("Profit Factor")
      .closest("div")?.parentElement;
    expect(profitFactorCard).toHaveTextContent("—");
  });

  it("handles string pnl_pct values", () => {
    const trades = [
      { pnl_pct: "5.5" },
      { pnl_pct: "-3.2" },
    ];

    render(<TradeDistributionChart trades={trades} profitFactor={null} />);

    expect(screen.getByText("Trade Distribution")).toBeInTheDocument();
  });

  it("filters out null pnl_pct values", () => {
    const trades = [
      { pnl_pct: 10.0 },
      { pnl_pct: null },
      { pnl_pct: -5.0 },
    ];

    render(<TradeDistributionChart trades={trades} profitFactor={null} />);

    // Should correctly calculate stats excluding null values
    // 1 win, 1 loss = 50% win rate
    expect(screen.getByText("(50.0%)")).toBeInTheDocument();
  });

  it("calculates correct win rate", () => {
    const trades = [
      { pnl_pct: 5.0 },
      { pnl_pct: 10.0 },
      { pnl_pct: 15.0 },
      { pnl_pct: -5.0 },
    ];

    render(<TradeDistributionChart trades={trades} profitFactor={null} />);

    // Win rate = 3/4 = 75.0%
    expect(screen.getByText("(75.0%)")).toBeInTheDocument();
  });

  it("renders the chart container", () => {
    const trades = [{ pnl_pct: 5.0 }];

    render(<TradeDistributionChart trades={trades} profitFactor={null} />);

    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
    expect(screen.getByTestId("bar-chart")).toBeInTheDocument();
  });

  it("displays color legend", () => {
    const trades = [{ pnl_pct: 5.0 }];

    render(<TradeDistributionChart trades={trades} profitFactor={null} />);

    expect(
      screen.getByText(/Green bars = winning trades/)
    ).toBeInTheDocument();
  });
});
