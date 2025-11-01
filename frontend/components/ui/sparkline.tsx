import * as React from "react";
import { cn } from "@/lib/utils";

interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  strokeWidth?: number;
  className?: string;
  variant?: "neutral" | "gain" | "loss";
  showDots?: boolean;
}

/**
 * Sparkline component for displaying 7-day score trends
 * Uses viz tokens and supports reduced-motion
 */
export function Sparkline({
  data,
  width = 100,
  height = 32,
  strokeWidth = 2,
  className,
  variant = "neutral",
  showDots = false,
}: SparklineProps) {
  // Handle empty or invalid data
  if (!data || data.length === 0) {
    return (
      <div
        className={cn("flex items-center justify-center", className)}
        style={{ width, height }}
      >
        <span className="text-xs text-text-muted">No data</span>
      </div>
    );
  }

  // Calculate min/max for scaling
  const minValue = Math.min(...data);
  const maxValue = Math.max(...data);
  const valueRange = maxValue - minValue || 1; // Avoid division by zero

  // Generate SVG path
  const points = data.map((value, index) => {
    // Handle single data point case (avoid division by zero)
    const x = data.length === 1 ? width / 2 : (index / (data.length - 1)) * width;
    const y = height - ((value - minValue) / valueRange) * height;
    return { x, y, value };
  });

  const pathData = points
    .map((point, index) => {
      const command = index === 0 ? "M" : "L";
      return `${command} ${point.x},${point.y}`;
    })
    .join(" ");

  // Determine color based on variant and trend
  const firstValue = data[0];
  const lastValue = data[data.length - 1];
  const trend = lastValue > firstValue ? "gain" : lastValue < firstValue ? "loss" : "neutral";
  const effectiveVariant = variant === "neutral" ? trend : variant;

  const strokeColorClass =
    effectiveVariant === "gain"
      ? "stroke-gain"
      : effectiveVariant === "loss"
        ? "stroke-loss"
        : "stroke-viz-3";

  const dotFillClass =
    effectiveVariant === "gain"
      ? "fill-gain"
      : effectiveVariant === "loss"
        ? "fill-loss"
        : "fill-viz-3";

  return (
    <svg
      width={width}
      height={height}
      className={cn("overflow-visible", className)}
      aria-label={`Sparkline chart with ${data.length} data points, trending ${trend}`}
    >
      {/* Line */}
      <path
        d={pathData}
        fill="none"
        className={cn(strokeColorClass, "transition-all duration-200")}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Dots at data points */}
      {showDots &&
        points.map((point, index) => (
          <circle
            key={index}
            cx={point.x}
            cy={point.y}
            r={strokeWidth}
            className={cn(
              dotFillClass,
              "transition-all duration-200 reduced-motion:transition-none"
            )}
          />
        ))}

      {/* Highlight first and last points */}
      <circle
        cx={points[0].x}
        cy={points[0].y}
        r={strokeWidth * 1.5}
        className={cn(
          dotFillClass,
          "opacity-50 transition-opacity duration-200 reduced-motion:transition-none"
        )}
      />
      <circle
        cx={points[points.length - 1].x}
        cy={points[points.length - 1].y}
        r={strokeWidth * 1.5}
        className={cn(
          dotFillClass,
          "transition-all duration-200 reduced-motion:transition-none"
        )}
      />
    </svg>
  );
}
