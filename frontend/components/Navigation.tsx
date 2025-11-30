"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Briefcase,
  Settings,
  Eye,
  Activity,
  Database,
  TrendingUp,
  BarChart3,
} from "lucide-react";

import { ThemeToggle } from "@/components/ThemeToggle";
import { cn } from "@/lib/utils";

const mainLinks = [
  {
    href: "/",
    label: "Dashboard",
    icon: LayoutDashboard,
  },
  {
    href: "/portfolio",
    label: "Portfolio",
    icon: Briefcase,
  },
  {
    href: "/watchlist",
    label: "Watchlist",
    icon: Eye,
  },
  {
    href: "/trading",
    label: "Trading",
    icon: TrendingUp,
  },
  {
    href: "/backtest",
    label: "Backtest",
    icon: BarChart3,
  },
  {
    href: "/capabilities",
    label: "Capabilities",
    icon: Database,
  },
];

const utilityLinks = [
  {
    href: "/status",
    label: "Status",
    icon: Activity,
  },
  {
    href: "/settings",
    label: "Settings",
    icon: Settings,
  },
];

export function Navigation() {
  const pathname = usePathname();

  return (
    <nav className="border-b border-border bg-surface">
      <div className="mx-auto h-16 max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-full items-center justify-between gap-4">
          {/* Logo */}
          <Link
            href="/"
            className="flex-shrink-0 rounded-md px-2 py-1 text-lg font-semibold text-text transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            Portfolio AI
          </Link>

          {/* Main Navigation */}
          <div className="flex items-center gap-0.5 sm:gap-1 rounded-full bg-surface-muted/40 p-1">
            {mainLinks.map((link) => {
              const Icon = link.icon;
              const isActive = pathname === link.href;

              return (
                <Link
                  key={link.href}
                  href={link.href}
                  aria-current={isActive ? "page" : undefined}
                  aria-label={link.label}
                  title={link.label}
                  className={cn(
                    "flex items-center gap-2 rounded-full px-2 sm:px-4 py-1.5 text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
                    isActive
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "text-text-muted hover:bg-surface-muted hover:text-text"
                  )}
                >
                  <Icon className="size-4" aria-hidden suppressHydrationWarning />
                  <span className="hidden sm:inline">{link.label}</span>
                </Link>
              );
            })}
          </div>

          {/* Utility Items */}
          <div className="flex items-center gap-0.5 sm:gap-1 rounded-full bg-surface-muted/40 p-1">
            {utilityLinks.map((link) => {
              const Icon = link.icon;
              const isActive = pathname === link.href;

              return (
                <Link
                  key={link.href}
                  href={link.href}
                  aria-current={isActive ? "page" : undefined}
                  aria-label={link.label}
                  title={link.label}
                  className={cn(
                    "flex items-center gap-2 rounded-full px-2 sm:px-4 py-1.5 text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
                    isActive
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "text-text-muted hover:bg-surface-muted hover:text-text"
                  )}
                >
                  <Icon className="size-4" aria-hidden suppressHydrationWarning />
                  <span className="hidden sm:inline">{link.label}</span>
                </Link>
              );
            })}
            <div className="mx-1 h-4 w-px bg-border/50" aria-hidden="true" />
            <ThemeToggle />
          </div>
        </div>
      </div>
    </nav>
  );
}
