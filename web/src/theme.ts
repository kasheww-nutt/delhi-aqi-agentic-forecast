import { useEffect, useState } from "react";

export type Theme = "dark" | "light";

/** Current value of a CSS custom property, for chart libraries that need literal colours. */
export const cssVar = (name: string) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";

/** Dark by default; the choice is remembered per browser (best effort). */
export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      return localStorage.getItem("aqi-theme") === "light" ? "light" : "dark";
    } catch {
      return "dark";
    }
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("aqi-theme", theme);
    } catch {
      /* private mode: the theme just isn't remembered */
    }
  }, [theme]);
  return [theme, () => setTheme(theme === "dark" ? "light" : "dark")];
}
