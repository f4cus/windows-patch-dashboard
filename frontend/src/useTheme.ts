import { useEffect, useLayoutEffect, useState } from "react";

export type ColorTheme = "light" | "dark";

export const THEME_STORAGE_KEY = "windows-patch-dashboard-theme";
const DARK_MODE_QUERY = "(prefers-color-scheme: dark)";

function readStoredTheme(): ColorTheme | null {
  try {
    const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
    return storedTheme === "light" || storedTheme === "dark"
      ? storedTheme
      : null;
  } catch {
    return null;
  }
}

function readSystemTheme(): ColorTheme {
  return window.matchMedia(DARK_MODE_QUERY).matches ? "dark" : "light";
}

export function resolveInitialTheme(): ColorTheme {
  return readStoredTheme() ?? readSystemTheme();
}

export function applyTheme(theme: ColorTheme): void {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
}

export function initializeTheme(): ColorTheme {
  const theme = resolveInitialTheme();
  applyTheme(theme);
  return theme;
}

export function useTheme() {
  const [theme, setTheme] = useState<ColorTheme>(resolveInitialTheme);
  const [hasExplicitPreference, setHasExplicitPreference] = useState(
    () => readStoredTheme() !== null,
  );

  useLayoutEffect(() => applyTheme(theme), [theme]);

  useEffect(() => {
    if (hasExplicitPreference) {
      return undefined;
    }

    const mediaQuery = window.matchMedia(DARK_MODE_QUERY);
    const followSystemTheme = (event: MediaQueryListEvent) => {
      setTheme(event.matches ? "dark" : "light");
    };

    mediaQuery.addEventListener("change", followSystemTheme);
    return () => mediaQuery.removeEventListener("change", followSystemTheme);
  }, [hasExplicitPreference]);

  function toggleTheme() {
    const nextTheme = theme === "light" ? "dark" : "light";
    setTheme(nextTheme);
    setHasExplicitPreference(true);

    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    } catch {
      // The active theme still changes when storage is unavailable.
    }
  }

  return { theme, toggleTheme } as const;
}
