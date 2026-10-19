import { describe, expect, it } from "vitest";
import { correctness, formatCost, formatLatency, formatMetric, formatPct, formatTokens, formatValue, isRateMetric } from "./format";

describe("formatMetric", () => {
  it("formats rates as mean [lo, hi] in percent", () => {
    expect(formatMetric({ mean: 0.6234, lo: 0.551, hi: 0.69 })).toBe("62.3% [55.1, 69.0]");
  });

  it("drops the interval when bounds are missing", () => {
    expect(formatMetric({ mean: 0.5, lo: null, hi: null })).toBe("50.0%");
  });

  it("shows a dash for missing metrics", () => {
    expect(formatMetric(undefined)).toBe("—");
    expect(formatMetric({ mean: null, lo: null, hi: null })).toBe("—");
  });

  it("supports non-rate metrics", () => {
    expect(formatMetric({ mean: 3.14159, lo: 2.5, hi: 3.9 }, { rate: false, digits: 2 })).toBe("3.14 [2.50, 3.90]");
  });

  it("knows which metrics are rates", () => {
    expect(isRateMetric("accuracy")).toBe(true);
    expect(isRateMetric("hallucination_rate")).toBe(true);
    expect(isRateMetric("tokens")).toBe(false);
  });
});

describe("number formatting", () => {
  it("percent", () => {
    expect(formatPct(0.05)).toBe("5.0%");
    expect(formatPct(null)).toBe("—");
  });

  it("tokens", () => {
    expect(formatTokens(4210)).toBe("4,210");
    expect(formatTokens(1_250_000)).toBe("1.25M");
  });

  it("latency", () => {
    expect(formatLatency(640)).toBe("640 ms");
    expect(formatLatency(6230)).toBe("6.23 s");
    expect(formatLatency(95_000)).toBe("1m 35s");
  });

  it("cost", () => {
    expect(formatCost(0)).toBe("$0");
    expect(formatCost(0.00042)).toBe("$0.00042");
    expect(formatCost(1.5)).toBe("$1.50");
  });

  it("values in base units", () => {
    expect(formatValue(25_785_000_000)).toBe("$25.79B");
    expect(formatValue(13.69, "%")).toBe("13.69%");
  });
});

describe("correctness", () => {
  it("maps 1/0 and judge scores to badge states", () => {
    expect(correctness(1)).toBe("correct");
    expect(correctness(0)).toBe("incorrect");
    expect(correctness(0.75)).toBe("partial");
    expect(correctness(0.25)).toBe("incorrect");
    expect(correctness(null)).toBe("ungraded");
  });
});
