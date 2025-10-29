"use client";

import { Monitor, Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  ThemePreference,
  useTheme,
} from "@/components/providers/ThemeProvider";

const ORDERED_THEMES: ThemePreference[] = ["dark", "light", "system"];

export function ThemeToggle() {
  const { theme, resolvedTheme, setTheme } = useTheme();

  const cycleTheme = () => {
    const currentIndex = ORDERED_THEMES.indexOf(theme);
    const nextTheme =
      ORDERED_THEMES[(currentIndex + 1) % ORDERED_THEMES.length];
    setTheme(nextTheme);
  };

  const title =
    theme === "system"
      ? `Theme: System (${resolvedTheme})`
      : `Theme: ${theme.charAt(0).toUpperCase() + theme.slice(1)}`;

  const icon =
    theme === "system" ? (
      <Monitor aria-hidden className="size-4" />
    ) : resolvedTheme === "light" ? (
      <Sun aria-hidden className="size-4" />
    ) : (
      <Moon aria-hidden className="size-4" />
    );

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      onClick={cycleTheme}
      title={`${title}. Click to cycle modes.`}
      aria-label={`${title}. Click to cycle modes.`}
      className="text-text-muted hover:bg-surface-muted/60 hover:text-text focus-visible:ring-2 focus-visible:ring-focus"
    >
      {icon}
      <span className="sr-only">{title}</span>
    </Button>
  );
}
