"use client";

import { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface ToggleCardProps {
  icon?: ReactNode;
  title: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  badge?: string;
  disabled?: boolean;
  className?: string;
}

export function ToggleCard({
  icon,
  title,
  description,
  checked,
  onChange,
  badge,
  disabled = false,
  className,
}: ToggleCardProps) {
  return (
    <button
      type="button"
      onClick={() => !disabled && onChange(!checked)}
      disabled={disabled}
      className={cn(
        "group relative flex w-full flex-col gap-3 rounded-lg border-2 p-4 text-left transition-all",
        checked
          ? "border-primary bg-primary/5"
          : "border-border bg-surface hover:border-border/60 hover:bg-surface-muted/30",
        disabled && "cursor-not-allowed opacity-50",
        className
      )}
    >
      {badge && (
        <Badge
          variant="secondary"
          className="absolute right-3 top-3 text-xs"
        >
          {badge}
        </Badge>
      )}

      <div className="flex items-start gap-3">
        {icon && (
          <div
            className={cn(
              "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg transition-colors",
              checked
                ? "bg-primary/20 text-primary"
                : "bg-surface-muted text-text-muted group-hover:bg-surface-muted/60"
            )}
          >
            {icon}
          </div>
        )}
        <div className="flex-1 space-y-1">
          <div className="flex items-center gap-2">
            <h4
              className={cn(
                "font-medium transition-colors",
                checked ? "text-text" : "text-text group-hover:text-text"
              )}
            >
              {title}
            </h4>
          </div>
          <p className="text-sm text-text-muted">{description}</p>
        </div>
      </div>

      {/* Checkmark indicator */}
      <div
        className={cn(
          "absolute bottom-3 right-3 flex h-5 w-5 items-center justify-center rounded-full border-2 transition-all",
          checked
            ? "border-primary bg-primary"
            : "border-border bg-surface group-hover:border-border/60"
        )}
      >
        {checked && (
          <svg
            className="h-3 w-3 text-primary-foreground"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={3}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M5 13l4 4L19 7"
            />
          </svg>
        )}
      </div>
    </button>
  );
}
