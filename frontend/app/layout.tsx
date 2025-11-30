import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import "./globals-watchlist.css";
import { Providers } from "./providers";
import { Toaster } from "sonner";
import { Navigation } from "@/components/Navigation";
import { cn } from "@/lib/utils";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Portfolio AI Platform",
  description: "AI-powered portfolio intelligence and market insights",
};

// Define theme constants directly to avoid serialization issues
const THEME_STORAGE_KEY = "portfolio-ai.theme";
const PREFERS_LIGHT_QUERY = "(prefers-color-scheme: light)";
const PREFERS_REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

const themeInitializer = `
(() => {
  try {
    const storageKey = "${THEME_STORAGE_KEY}";
    const systemQuery = window.matchMedia("${PREFERS_LIGHT_QUERY}");
    const motionQuery = window.matchMedia("${PREFERS_REDUCED_MOTION_QUERY}");
    const stored = window.localStorage.getItem(storageKey);
    const theme = stored === "light" || stored === "dark" || stored === "system" ? stored : "system";
    const resolved = theme === "system" ? (systemQuery.matches ? "light" : "dark") : theme;
    const root = document.documentElement;
    if (resolved === "light") {
      root.classList.add("light");
      root.classList.remove("dark");
    } else {
      root.classList.add("dark");
      root.classList.remove("light");
    }
    root.dataset.theme = resolved;
    root.style.colorScheme = resolved;
    root.dataset.reducedMotion = motionQuery.matches ? "true" : "false";
  } catch (_) {
    /* no-op */
  }
})();`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        className={cn(
          geistSans.variable,
          geistMono.variable,
          "bg-bg text-text antialiased"
        )}
        suppressHydrationWarning
      >
        <script
          suppressHydrationWarning
          dangerouslySetInnerHTML={{ __html: themeInitializer }}
        />
        <Providers>
          <Navigation />
          <main>{children}</main>
          <Toaster position="top-right" richColors />
        </Providers>
      </body>
    </html>
  );
}
