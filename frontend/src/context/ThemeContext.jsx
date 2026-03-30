import { createContext, useContext, useState, useCallback } from "react";
import { darkColors, lightColors } from "../styles/theme";

const ThemeContext = createContext();

/**
 * ThemeProvider — wraps the app and provides { colors, isDark, toggleTheme }
 * to all descendants via useTheme().
 *
 * Persists preference in localStorage so it survives page reloads.
 */
export function ThemeProvider({ children }) {
  const [isDark, setIsDark] = useState(() => {
    try {
      return localStorage.getItem("re-theme") !== "light";
    } catch {
      return true; // default to dark
    }
  });

  const toggleTheme = useCallback(() => {
    setIsDark((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("re-theme", next ? "dark" : "light");
      } catch {
        // localStorage unavailable — no-op
      }
      return next;
    });
  }, []);

  const colors = isDark ? darkColors : lightColors;

  return (
    <ThemeContext.Provider value={{ colors, isDark, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

/**
 * useTheme — returns { colors, isDark, toggleTheme } from the nearest ThemeProvider.
 */
export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return ctx;
}
