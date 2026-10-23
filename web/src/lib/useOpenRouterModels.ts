import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { OpenRouterModel } from "../api/types";

let cache: Promise<OpenRouterModel[]> | null = null;

/** Loads /api/openrouter/models once per page load and shares it across pickers. */
export function loadOpenRouterModels(force = false): Promise<OpenRouterModel[]> {
  if (!cache || force) {
    cache = api.openrouterModels().then((r) => r.models);
    cache.catch(() => {
      cache = null; // allow a retry after a failure (e.g. HTTP 502)
    });
  }
  return cache;
}

export function useOpenRouterModels(): { models: OpenRouterModel[] | undefined; error: Error | undefined; loading: boolean } {
  const [models, setModels] = useState<OpenRouterModel[]>();
  const [error, setError] = useState<Error>();
  useEffect(() => {
    let live = true;
    loadOpenRouterModels()
      .then((m) => live && setModels(m))
      .catch((e: unknown) => live && setError(e instanceof Error ? e : new Error(String(e))));
    return () => {
      live = false;
    };
  }, []);
  return { models, error, loading: !models && !error };
}
