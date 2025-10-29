import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { Toaster } from "sonner";
import { Navigation } from "@/components/Navigation";
import { cn } from "@/lib/utils";
import {
  PREFERS_LIGHT_QUERY,
  PREFERS_REDUCED_MOTION_QUERY,
  THEME_STORAGE_KEY,
} from "@/components/providers/ThemeProvider";

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
      >
        <script
          suppressHydrationWarning
          dangerouslySetInnerHTML={{ __html: themeInitializer }}
        />
        <Providers>
          <Navigation />
          {children}
          <Toaster position="top-right" richColors />
        </Providers>
      </body>
    </html>
  );
}
