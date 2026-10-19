import { createContext, useContext } from "react";
import type { Citation, Evidence } from "../api/types";

/** What a citation chip hands to the drawer. */
export interface CitationTarget {
  /** The evidence id as written in the answer, e.g. "E3". */
  id: string;
  /** The ledger item, when the answer has one with this id. */
  evidence?: Evidence;
  /** Fallback when only a claim citation is known (no ledger item). */
  citation?: Citation;
  /** Verifier verdict for the claim the chip sits in (undefined = opened outside a claim). */
  verified?: boolean | null;
}

export interface CitationContextValue {
  open: (target: CitationTarget) => void;
  close: () => void;
  current: CitationTarget | null;
}

export const CitationContext = createContext<CitationContextValue>({
  open: () => {},
  close: () => {},
  current: null,
});

export function useCitation(): CitationContextValue {
  return useContext(CitationContext);
}
