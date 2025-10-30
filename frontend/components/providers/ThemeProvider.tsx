"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  startTransition,
  useRef,
} from "react";

export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export const THEME_STORAGE_KEY = "portfolio-ai.theme";
export const PREFERS_LIGHT_QUERY = "(prefers-color-scheme: light)";
export const PREFERS_REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

const ThemeContext = createContext<{
  theme: ThemePreference;
  resolvedTheme: ResolvedTheme;
  prefersReducedMotion: boolean;
  setTheme: (value: ThemePreference) => void;
} | null>(null);

function applyThemeToDocument(theme: ResolvedTheme) {
  const root = document.documentElement;

  if (theme === "light") {
    root.classList.add("light");
    root.classList.remove("dark");
  } else {
    root.classList.add("dark");
    root.classList.remove("light");
  }

  root.dataset.theme = theme;
  root.style.setProperty("color-scheme", theme);
}

function applyMotionPreference(reduced: boolean) {
  const root = document.documentElement;
  root.dataset.reducedMotion = reduced ? "true" : "false";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<ThemePreference>("dark");
  const [systemTheme, setSystemTheme] = useState<ResolvedTheme>("dark");
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>("dark");
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const isInitializedRef = useRef(false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const storedTheme = window.localStorage.getItem(
      THEME_STORAGE_KEY
    ) as ThemePreference | null;

    if (
      storedTheme === "light" ||
      storedTheme === "dark" ||
      storedTheme === "system"
    ) {
      startTransition(() => {
        setThemeState(storedTheme);
      });
    }

    const systemMedia = window.matchMedia(PREFERS_LIGHT_QUERY);
    const handleSystem = (event?: MediaQueryListEvent) => {
      const isLight = event ? event.matches : systemMedia.matches;
      startTransition(() => {
        setSystemTheme(isLight ? "light" : "dark");
      });
    };

    handleSystem();
    systemMedia.addEventListener("change", handleSystem);

    const motionMedia = window.matchMedia(PREFERS_REDUCED_MOTION_QUERY);
    const handleMotion = (event?: MediaQueryListEvent) => {
      const prefersReduced = event ? event.matches : motionMedia.matches;
      startTransition(() => {
        setPrefersReducedMotion(prefersReduced);
      });
      applyMotionPreference(prefersReduced);
    };

    handleMotion();
    motionMedia.addEventListener("change", handleMotion);

    isInitializedRef.current = true;

    return () => {
      systemMedia.removeEventListener("change", handleSystem);
      motionMedia.removeEventListener("change", handleMotion);
    };
  }, []);

  useEffect(() => {
    if (!isInitializedRef.current || typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  useEffect(() => {
    if (!isInitializedRef.current) {
      return;
    }

    const nextResolved: ResolvedTheme =
      theme === "system" ? systemTheme : theme;

    startTransition(() => {
      setResolvedTheme((prev) => {
        if (prev !== nextResolved) {
          applyThemeToDocument(nextResolved);
        }
        return nextResolved;
      });
    });
  }, [theme, systemTheme]);

  useEffect(() => {
    if (!isInitializedRef.current) {
      return;
    }

    applyMotionPreference(prefersReducedMotion);
  }, [prefersReducedMotion]);

  const setTheme = useCallback((value: ThemePreference) => {
    setThemeState(value);
  }, []);

  const contextValue = useMemo(
    () => ({
      theme,
      resolvedTheme,
      prefersReducedMotion,
      setTheme,
    }),
    [theme, resolvedTheme, prefersReducedMotion, setTheme]
  );

  return (
    <ThemeContext.Provider value={contextValue}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);

  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }

  return context;
}
