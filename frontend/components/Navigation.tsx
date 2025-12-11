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
  Bot,
  Brain,
  Target,
  HardDrive,
} from "lucide-react";

import { MarketStatusBadge } from "@/components/market/MarketStatusBadge";
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
    href: "/strategies",
    label: "Strategies",
    icon: Brain,
  },
  {
    href: "/recommendations",
    label: "Recs",
    icon: Target,
  },
  {
    href: "/capabilities",
    label: "Capabilities",
    icon: Database,
  },
];

const utilityLinks = [
  {
    href: "/agents",
    label: "Agents",
    icon: Bot,
  },
  {
    href: "/status",
    label: "Status",
    icon: Activity,
  },
  {
    href: "/backup",
    label: "Backup",
    icon: HardDrive,
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
    <nav className="sticky top-0 z-50 border-b border-border/50 bg-surface/80 backdrop-blur-md supports-[backdrop-filter]:bg-surface/60">
      <div className="mx-auto h-16 w-full px-4 sm:px-6 lg:px-8">
        <div className="flex h-full items-center justify-between">
          {/* Logo */}
          <div className="flex items-center">
            <Link
              href="/"
              className="flex-shrink-0 rounded-md px-2 py-1 text-lg font-bold tracking-tight text-text transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              Portfolio AI
            </Link>
          </div>

          {/* Main Navigation - Centered */}
          <div className="hidden lg:flex absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
            <div className="flex items-center gap-1 rounded-full bg-surface-muted/50 border border-border/50 p-1 shadow-sm backdrop-blur-sm">
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
                      "group flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
                      isActive
                        ? "bg-primary text-primary-foreground shadow-md"
                        : "text-text-muted hover:bg-surface hover:text-text hover:shadow-sm"
                    )}
                  >
                    <Icon className={cn("size-4 transition-transform group-hover:scale-110", isActive && "text-primary-foreground")} aria-hidden suppressHydrationWarning />
                    <span>{link.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>

          {/* Utility Items */}
          <div className="flex items-center gap-1 sm:gap-2">
            <div className="flex items-center gap-0.5 rounded-full bg-surface-muted/50 border border-border/50 p-1 shadow-sm backdrop-blur-sm">
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
                      "group flex items-center justify-center rounded-full p-2 text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
                      isActive
                        ? "bg-primary text-primary-foreground shadow-sm"
                        : "text-text-muted hover:bg-surface hover:text-text hover:shadow-sm"
                    )}
                  >
                    <Icon className="size-4" aria-hidden suppressHydrationWarning />
                  </Link>
                );
              })}
            </div>
            <div className="hidden sm:block">
              <MarketStatusBadge />
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
