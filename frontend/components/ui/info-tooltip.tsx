/**
 * InfoTooltip Component
 *
 * Educational tooltip with info icon that reveals explanation on hover.
 * Designed for plain-language education about market terms.
 */

"use client";

import * as React from "react";
import { InfoIcon } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export interface InfoTooltipProps {
  /**
   * Tooltip content (educational explanation)
   */
  content: string;

  /**
   * Side to display tooltip
   */
  side?: "top" | "right" | "bottom" | "left";

  /**
   * Additional CSS classes for the trigger icon
   */
  className?: string;

  /**
   * Icon size (default: 14px)
   */
  iconSize?: number;
}

export function InfoTooltip({
  content,
  side = "top",
  className,
  iconSize = 14,
}: InfoTooltipProps) {
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className={cn(
              "inline-flex items-center justify-center",
              "text-text-muted hover:text-text",
              "transition-colors duration-150",
              "focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-bg",
              "rounded-full",
              className
            )}
            aria-label="Information"
          >
            <InfoIcon size={iconSize} />
          </button>
        </TooltipTrigger>
        <TooltipContent
          side={side}
          className="max-w-[250px] text-sm leading-relaxed"
        >
          {content}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
