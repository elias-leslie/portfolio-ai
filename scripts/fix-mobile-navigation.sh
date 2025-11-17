#!/bin/bash
# Fix mobile navigation - hide labels on small screens
# Run with: sudo bash scripts/fix-mobile-navigation.sh

set -e

echo "================================"
echo "Fixing Mobile Navigation"
echo "================================"
echo ""

NAV_FILE="/home/kasadis/portfolio-ai/frontend/components/Navigation.tsx"

echo "1. Creating backup..."
cp "$NAV_FILE" "${NAV_FILE}.backup-$(date +%Y%m%d-%H%M%S)"
echo "   ✓ Backup created"

echo "2. Applying mobile-responsive fixes..."
# Use sudo to run as portfolio-ai user
sudo -u portfolio-ai bash -c "cat > '$NAV_FILE' << 'EOF'
\"use client\";

import Link from \"next/link\";
import { usePathname } from \"next/navigation\";
import {
  LayoutDashboard,
  Briefcase,
  Settings,
  Eye,
  Activity,
  Database,
} from \"lucide-react\";

import { ThemeToggle } from \"@/components/ThemeToggle\";
import { cn } from \"@/lib/utils\";

const links = [
  {
    href: \"/\",
    label: \"Dashboard\",
    icon: LayoutDashboard,
  },
  {
    href: \"/portfolio\",
    label: \"Portfolio\",
    icon: Briefcase,
  },
  {
    href: \"/watchlist\",
    label: \"Watchlist\",
    icon: Eye,
  },
  {
    href: \"/capabilities\",
    label: \"Capabilities\",
    icon: Database,
  },
  {
    href: \"/status\",
    label: \"Status\",
    icon: Activity,
  },
  {
    href: \"/settings\",
    label: \"Settings\",
    icon: Settings,
  },
];

export function Navigation() {
  const pathname = usePathname();

  return (
    <nav className=\"border-b border-border bg-surface\">
      <div className=\"mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8\">
        <Link
          href=\"/\"
          className=\"rounded-md px-2 py-1 text-lg font-semibold text-text transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus\"
        >
          Portfolio AI
        </Link>

        <div className=\"flex items-center gap-2\">
          <div className=\"flex items-center gap-0.5 sm:gap-1 rounded-full bg-surface-muted/40 p-1\">
            {links.map((link) => {
              const Icon = link.icon;
              const isActive = pathname === link.href;

              return (
                <Link
                  key={link.href}
                  href={link.href}
                  aria-current={isActive ? \"page\" : undefined}
                  aria-label={link.label}
                  title={link.label}
                  className={cn(
                    \"flex items-center gap-2 rounded-full px-2 sm:px-4 py-1.5 text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus\",
                    isActive
                      ? \"bg-primary text-primary-foreground shadow-sm\"
                      : \"text-text-muted hover:bg-surface-muted hover:text-text\"
                  )}
                >
                  <Icon className=\"size-4\" aria-hidden />
                  <span className=\"hidden sm:inline\">{link.label}</span>
                </Link>
              );
            })}
          </div>
          <ThemeToggle />
        </div>
      </div>
    </nav>
  );
}
EOF
"

echo "   ✓ Mobile fixes applied"

echo "3. Restarting frontend service..."
bash /home/kasadis/portfolio-ai/scripts/restart.sh | grep -A 5 "Frontend"
sleep 5

echo ""
echo "================================"
echo "Fix Complete!"
echo "================================"
echo ""
echo "Changes made:"
echo "  - Labels hidden on mobile (< 640px width)"
echo "  - Icons only visible on small screens"
echo "  - Full labels + icons on tablets/desktop"
echo "  - Reduced padding/spacing on mobile"
echo ""
echo "Test on your phone: http://100.123.190.81:3000"
echo "Should no longer require horizontal scrolling!"
echo ""
