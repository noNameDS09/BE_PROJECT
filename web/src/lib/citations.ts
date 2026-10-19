import type { Claim } from "../api/types";

/** A piece of answer text: plain text, or a citation marker such as [E3]. */
export type Token = { type: "text"; value: string } | { type: "cite"; id: string };

/**
 * Matches [E1], [E1, E2], [E1; E12] and tolerates a lower-case e. Adjacent markers such as
 * [E1][E2] are two matches.
 */
const MARKER = /\[\s*([Ee]\d+(?:\s*[,;]\s*[Ee]\d+)*)\s*\]/g;

/** Splits text into text and citation tokens. Evidence ids are normalised to "E<n>". */
export function parseCitations(text: string): Token[] {
  const tokens: Token[] = [];
  let last = 0;
  for (const match of text.matchAll(MARKER)) {
    const index = match.index ?? 0;
    if (index > last) tokens.push({ type: "text", value: text.slice(last, index) });
    const ids = (match[1] ?? "").split(/[,;]/).map((s) => s.trim().toUpperCase());
    for (const id of ids) if (id) tokens.push({ type: "cite", id });
    last = index + match[0].length;
  }
  if (last < text.length) tokens.push({ type: "text", value: text.slice(last) });
  return tokens;
}

/** The distinct evidence ids cited in a text, in first-seen order. */
export function citedIds(text: string): string[] {
  const seen = new Set<string>();
  for (const t of parseCitations(text)) if (t.type === "cite") seen.add(t.id);
  return [...seen];
}

/** A stretch of the answer text, attributed to the claim it belongs to (or to none). */
export interface Segment {
  text: string;
  claim: number | null;
}

/**
 * Locates each claim's text inside the answer text, in order, so the answer can be shown as
 * written with claims highlighted. Matching ignores whitespace differences. Returns null when
 * any claim cannot be found (the caller then shows the claims as a list instead).
 */
export function segmentAnswer(text: string, claims: Claim[]): Segment[] | null {
  if (claims.length === 0) return [{ text, claim: null }];
  const segments: Segment[] = [];
  let cursor = 0;
  for (let i = 0; i < claims.length; i++) {
    const found = findLoose(text, (claims[i] as Claim).text, cursor);
    if (!found) return null;
    const [start, end] = found;
    if (start > cursor) segments.push({ text: text.slice(cursor, start), claim: null });
    segments.push({ text: text.slice(start, end), claim: i });
    cursor = end;
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor), claim: null });
  return segments;
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Finds `needle` in `hay` from `from`, treating any run of whitespace as equal. */
function findLoose(hay: string, needle: string, from: number): [number, number] | null {
  const trimmed = needle.trim();
  if (!trimmed) return null;
  const exact = hay.indexOf(trimmed, from);
  if (exact >= 0) return [exact, exact + trimmed.length];
  const pattern = trimmed.split(/\s+/).map(escapeRegExp).join("\\s+");
  const re = new RegExp(pattern, "g");
  re.lastIndex = from;
  const m = re.exec(hay);
  return m ? [m.index, m.index + m[0].length] : null;
}

export type ClaimStatus = "supported" | "unsupported" | "unchecked";

export function claimStatus(claim: Pick<Claim, "supported">): ClaimStatus {
  if (claim.supported === true) return "supported";
  if (claim.supported === false) return "unsupported";
  return "unchecked";
}

/** Counts of claim verdicts, for the column header. */
export function claimSummary(claims: Claim[]): Record<ClaimStatus, number> {
  const out: Record<ClaimStatus, number> = { supported: 0, unsupported: 0, unchecked: 0 };
  for (const c of claims) out[claimStatus(c)] += 1;
  return out;
}
