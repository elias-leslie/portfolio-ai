import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MonthlyReturnsHeatmap } from "../MonthlyReturnsHeatmap";

describe("MonthlyReturnsHeatmap", () => {
  it("returns null for empty equity curve", () => {
    const { container } = render(<MonthlyReturnsHeatmap equityCurve={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("returns null for single data point", () => {
    const { container } = render(
      <MonthlyReturnsHeatmap
        equityCurve={[{ date: "2024-01-15", equity: 10000 }]}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders heatmap with valid equity curve", () => {
    const equityCurve = [
      { date: "2024-01-01", equity: 10000 },
      { date: "2024-01-15", equity: 10500 },
      { date: "2024-01-31", equity: 11000 },
      { date: "2024-02-01", equity: 11000 },
      { date: "2024-02-28", equity: 10500 },
    ];

    render(<MonthlyReturnsHeatmap equityCurve={equityCurve} />);

    expect(screen.getByText("Monthly Returns Heatmap")).toBeInTheDocument();
    expect(screen.getByText("2024")).toBeInTheDocument();
  });

  it("handles string equity values", () => {
    const equityCurve = [
      { date: "2024-01-01", equity: "10000" },
      { date: "2024-01-31", equity: "11000" },
    ];

    render(<MonthlyReturnsHeatmap equityCurve={equityCurve} />);

    expect(screen.getByText("Monthly Returns Heatmap")).toBeInTheDocument();
  });

  it("displays all month headers", () => {
    const equityCurve = [
      { date: "2024-01-01", equity: 10000 },
      { date: "2024-12-31", equity: 12000 },
    ];

    render(<MonthlyReturnsHeatmap equityCurve={equityCurve} />);

    expect(screen.getByText("Jan")).toBeInTheDocument();
    expect(screen.getByText("Feb")).toBeInTheDocument();
    expect(screen.getByText("Dec")).toBeInTheDocument();
  });

  it("displays yearly total column", () => {
    const equityCurve = [
      { date: "2024-01-01", equity: 10000 },
      { date: "2024-01-31", equity: 11000 },
    ];

    render(<MonthlyReturnsHeatmap equityCurve={equityCurve} />);

    expect(screen.getByText("Total")).toBeInTheDocument();
  });

  it("displays color legend", () => {
    const equityCurve = [
      { date: "2024-01-01", equity: 10000 },
      { date: "2024-01-31", equity: 11000 },
    ];

    render(<MonthlyReturnsHeatmap equityCurve={equityCurve} />);

    expect(
      screen.getByText(/Green = positive returns/)
    ).toBeInTheDocument();
  });

  it("shows positive returns with green color", () => {
    const equityCurve = [
      { date: "2024-01-01", equity: 10000 },
      { date: "2024-01-31", equity: 11000 }, // +10%
    ];

    const { container } = render(
      <MonthlyReturnsHeatmap equityCurve={equityCurve} />
    );

    // Should have green-colored cells for positive returns
    const greenCells = container.querySelectorAll('[class*="bg-green"]');
    expect(greenCells.length).toBeGreaterThan(0);
  });

  it("handles multiple years", () => {
    const equityCurve = [
      { date: "2023-01-01", equity: 10000 },
      { date: "2023-01-31", equity: 10500 },
      { date: "2024-01-01", equity: 11000 },
      { date: "2024-01-31", equity: 11500 },
    ];

    render(<MonthlyReturnsHeatmap equityCurve={equityCurve} />);

    expect(screen.getByText("2023")).toBeInTheDocument();
    expect(screen.getByText("2024")).toBeInTheDocument();
  });
});
