"use client";

import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface SectionHeaderProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  badge?: ReactNode;
  className?: string;
}

export function SectionHeader({
  icon,
  title,
  description,
  badge,
  className,
}: SectionHeaderProps) {
  return (
    <div className={cn("mb-6 flex items-start gap-4", className)}>
      {icon && (
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
          {icon}
        </div>
      )}
      <div className="flex-1">
        <div className="flex items-center gap-3">
          <h2 className="text-2xl font-semibold text-text">{title}</h2>
          {badge}
        </div>
        {description && (
          <p className="mt-1 text-sm text-text-muted">{description}</p>
        )}
      </div>
    </div>
  );
}
