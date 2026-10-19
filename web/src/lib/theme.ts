import { useCallback, useEffect, useState } from "react";

export type ThemePref = "system" | "light" | "dark";
const KEY = "loupe-theme";

function readPref(): ThemePref {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

function systemDark(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches;
}

/** The theme actually in effect. */
export function resolvedTheme(pref: ThemePref): "light" | "dark" {
  if (pref === "system") return systemDark() ? "dark" : "light";
  return pref;
}

/**
 * Theme preference: "system" follows prefers-color-scheme (CSS media query); "light"/"dark"
 * set data-theme on <html>. Emits a "loupe-theme" event so charts can re-theme.
 */
export function useTheme(): { pref: ThemePref; theme: "light" | "dark"; cycle: () => void } {
  const [pref, setPref] = useState<ThemePref>(readPref);
  const [, force] = useState(0);

  useEffect(() => {
    const root = document.documentElement;
    if (pref === "system") delete root.dataset.theme;
    else root.dataset.theme = pref;
    try {
      if (pref === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, pref);
    } catch {
      /* storage unavailable */
    }
    window.dispatchEvent(new Event("loupe-theme"));
  }, [pref]);

  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!mq) return;
    const onChange = () => {
      force((n) => n + 1);
      window.dispatchEvent(new Event("loupe-theme"));
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const cycle = useCallback(() => {
    setPref((p) => (p === "system" ? "light" : p === "light" ? "dark" : "system"));
  }, []);

  return { pref, theme: resolvedTheme(pref), cycle };
}

/** Re-renders the caller when the effective theme changes. */
export function useThemeVersion(): number {
  const [v, setV] = useState(0);
  useEffect(() => {
    const on = () => setV((n) => n + 1);
    window.addEventListener("loupe-theme", on);
    return () => window.removeEventListener("loupe-theme", on);
  }, []);
  return v;
}
