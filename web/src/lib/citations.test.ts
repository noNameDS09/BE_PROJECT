import { describe, expect, it } from "vitest";
import type { Claim } from "../api/types";
import { citedIds, claimStatus, claimSummary, parseCitations, segmentAnswer, sourceLinkLabel } from "./citations";

const claim = (text: string, supported: boolean | null = true): Claim => ({ text, citations: [], supported });

describe("parseCitations", () => {
  it("splits text and single markers", () => {
    expect(parseCitations("Revenue was $25.8B [E1].")).toEqual([
      { type: "text", value: "Revenue was $25.8B " },
      { type: "cite", id: "E1" },
      { type: "text", value: "." },
    ]);
  });

  it("handles adjacent, grouped and lower-case markers", () => {
    const tokens = parseCitations("Up 14% [E2][E3], see [E4, e12; E5]");
    expect(tokens.filter((t) => t.type === "cite").map((t) => (t.type === "cite" ? t.id : ""))).toEqual(["E2", "E3", "E4", "E12", "E5"]);
  });

  it("leaves non-evidence brackets alone", () => {
    expect(parseCitations("Item [1A] and [Note 7]")).toEqual([{ type: "text", value: "Item [1A] and [Note 7]" }]);
  });

  it("returns no tokens for empty text", () => {
    expect(parseCitations("")).toEqual([]);
  });

  it("citedIds de-duplicates in first-seen order", () => {
    expect(citedIds("[E2] a [E1] b [E2]")).toEqual(["E2", "E1"]);
  });
});

describe("segmentAnswer", () => {
  it("locates claims in order and keeps the text between them", () => {
    const text = "A is 1 [E1]. B is 2 [E2]. Ask again later.";
    const segs = segmentAnswer(text, [claim("A is 1 [E1]."), claim("B is 2 [E2].", false)]);
    expect(segs).toEqual([
      { text: "A is 1 [E1].", claim: 0 },
      { text: " ", claim: null },
      { text: "B is 2 [E2].", claim: 1 },
      { text: " Ask again later.", claim: null },
    ]);
    expect(segs?.map((s) => s.text).join("")).toBe(text);
  });

  it("tolerates whitespace differences", () => {
    const segs = segmentAnswer("Revenue  was\n$5M [E1].", [claim("Revenue was $5M [E1].")]);
    expect(segs?.[0]).toEqual({ text: "Revenue  was\n$5M [E1].", claim: 0 });
  });

  it("returns null when a claim is not in the text", () => {
    expect(segmentAnswer("Something else.", [claim("Not here.")])).toBeNull();
  });

  it("returns the whole text when there are no claims", () => {
    expect(segmentAnswer("Plain.", [])).toEqual([{ text: "Plain.", claim: null }]);
  });
});

describe("claim status", () => {
  it("maps supported to a verdict and counts them", () => {
    expect(claimStatus({ supported: true })).toBe("supported");
    expect(claimStatus({ supported: false })).toBe("unsupported");
    expect(claimStatus({ supported: null })).toBe("unchecked");
    expect(claimSummary([claim("a", true), claim("b", false), claim("c", null), claim("d", true)])).toEqual({
      supported: 2,
      unsupported: 1,
      unchecked: 1,
    });
  });
});

describe("sourceLinkLabel", () => {
  it("names SEC's inline XBRL viewer for /ix?doc= links and the filing otherwise", () => {
    expect(sourceLinkLabel("https://www.sec.gov/ix?doc=/Archives/edgar/data/2488/x/amd-20241228.htm")).toBe("Open in SEC inline XBRL viewer");
    expect(sourceLinkLabel("https://www.sec.gov/Archives/edgar/data/2488/000000248825000012/")).toBe("Open filing");
  });
});
