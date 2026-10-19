import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { ConfigResponse } from "../api/types";
import { armRank, armShort } from "./arms";

let cache: Promise<ConfigResponse> | null = null;

/** Loads /api/config once per page load and shares it. */
export function loadConfig(force = false): Promise<ConfigResponse> {
  if (!cache || force) {
    cache = api.config().then((c) => ({ ...c, arms: [...c.arms].sort((a, b) => armRank(a.name) - armRank(b.name)) }));
    cache.catch(() => {
      cache = null; // allow a retry after a failure
    });
  }
  return cache;
}

export function useConfig(): { config: ConfigResponse | undefined; error: Error | undefined; retry: () => void } {
  const [config, setConfig] = useState<ConfigResponse>();
  const [error, setError] = useState<Error>();
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    setError(undefined);
    loadConfig(tick > 0)
      .then((c) => live && setConfig(c))
      .catch((e: unknown) => live && setError(e instanceof Error ? e : new Error(String(e))));
    return () => {
      live = false;
    };
  }, [tick]);
  return { config, error, retry: () => setTick((t) => t + 1) };
}

/** Human label for an arm, from /config when available. */
export function armLabel(config: ConfigResponse | undefined, arm: string): string {
  return config?.arms.find((a) => a.name === arm)?.label ?? armShort(arm);
}
