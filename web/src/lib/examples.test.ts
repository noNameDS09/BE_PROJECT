import { describe, expect, it } from "vitest";
import { DEMO_ARMS, DEMO_QUESTIONS, EXAMPLE_QUESTIONS, datasetOf, findDemo } from "./examples";

describe("DEMO_QUESTIONS", () => {
  it("has ten demos with unique ids and every field filled in", () => {
    expect(DEMO_QUESTIONS).toHaveLength(10);
    expect(new Set(DEMO_QUESTIONS.map((d) => d.id)).size).toBe(10);
    for (const d of DEMO_QUESTIONS) {
      expect(d.id).toMatch(/^[a-z0-9-]+$/);
      for (const field of [d.title, d.question, d.shows, d.lookFor]) expect(field.trim()).toBe(field);
      expect(d.title.split(/\s+/).length).toBeLessThanOrEqual(3);
      expect(d.question).toMatch(/[?.]$/);
      expect(d.shows.length).toBeGreaterThan(0);
      expect(d.lookFor.length).toBeGreaterThan(0);
      expect(d.lookFor.length).toBeLessThan(140);
    }
  });

  it("derives EXAMPLE_QUESTIONS and finds demos by question", () => {
    expect(EXAMPLE_QUESTIONS).toEqual(DEMO_QUESTIONS.map((d) => d.question));
    expect(findDemo(`  ${DEMO_QUESTIONS[8]!.question} `)?.id).toBe("false-premise");
    expect(findDemo("Something else?")).toBeUndefined();
    expect(findDemo("")).toBeUndefined();
  });

  it("runs demos on B0, ReAct and Loupe", () => {
    expect([...DEMO_ARMS]).toEqual(["b0", "react", "loupe"]);
  });
});

describe("datasetOf", () => {
  it("reads the dataset from an item id", () => {
    expect(datasetOf("loupe-gold:amd-rev")).toBe("loupe-gold");
    expect(datasetOf("plain")).toBe("plain");
  });
});
