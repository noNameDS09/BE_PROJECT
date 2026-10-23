import { describe, expect, it } from "vitest";
import { classifyModelValue, formatContext, lacksToolCalling, openRouterId, openRouterLabel, shortModelName, toOpenRouterAlias } from "./modelPicker";

describe("toOpenRouterAlias", () => {
  it("prefixes a typed id and trims it", () => {
    expect(toOpenRouterAlias("qwen/qwen3-235b-a22b:free")).toBe("openrouter/qwen/qwen3-235b-a22b:free");
    expect(toOpenRouterAlias("  google/gemma-4-31b-it:free \n")).toBe("openrouter/google/gemma-4-31b-it:free");
  });

  it("strips a pasted openrouter/ prefix", () => {
    expect(toOpenRouterAlias("openrouter/qwen/qwen3-235b-a22b:free")).toBe("openrouter/qwen/qwen3-235b-a22b:free");
    expect(toOpenRouterAlias("OpenRouter/qwen/qwen3")).toBe("openrouter/qwen/qwen3");
  });

  it("keeps OpenRouter's own ids such as openrouter/free", () => {
    expect(toOpenRouterAlias("openrouter/free")).toBe("openrouter/openrouter/free");
    expect(toOpenRouterAlias("openrouter/openrouter/free")).toBe("openrouter/openrouter/free");
  });

  it("returns an empty string for blank input", () => {
    expect(toOpenRouterAlias("")).toBe("");
    expect(toOpenRouterAlias("   ")).toBe("");
  });

  it("round-trips through openRouterId", () => {
    for (const alias of ["openrouter/qwen/qwen3-235b-a22b:free", "openrouter/openrouter/free"]) {
      expect(toOpenRouterAlias(openRouterId(alias))).toBe(alias);
    }
    expect(openRouterId("gemini-flash")).toBe("");
  });
});

describe("classifyModelValue", () => {
  const configured = ["gemini-flash", "or-gemma-4-31b"];
  const live = ["openrouter/google/gemma-4-31b-it:free"];

  it("finds configured and live models", () => {
    expect(classifyModelValue("gemini-flash", configured, live)).toBe("configured");
    expect(classifyModelValue("openrouter/google/gemma-4-31b-it:free", configured, live)).toBe("openrouter");
  });

  it("treats an OpenRouter alias in neither list as custom", () => {
    expect(classifyModelValue("openrouter/qwen/qwen3-235b-a22b:free", configured, live)).toBe("custom");
    expect(classifyModelValue("openrouter/qwen/qwen3-235b-a22b:free", configured, [])).toBe("custom"); // list failed to load
  });

  it("waits for the live list before calling an OpenRouter alias custom", () => {
    expect(classifyModelValue("openrouter/google/gemma-4-31b-it:free", configured, null)).toBe("pending");
  });

  it("flags other unknown aliases", () => {
    expect(classifyModelValue("retired-model", configured, live)).toBe("unknown");
  });
});

describe("labels", () => {
  it("formats context lengths in k (or M)", () => {
    expect(formatContext(262144)).toBe("262k");
    expect(formatContext(131072)).toBe("131k");
    expect(formatContext(1048576)).toBe("1M");
    expect(formatContext(null)).toBe("");
  });

  it("shortens OpenRouter names and marks models without tools", () => {
    expect(shortModelName("Google: Gemma 4 31B (free)")).toBe("Gemma 4 31B");
    expect(shortModelName("Google: Gemma 4 26B A4B  (free)")).toBe("Gemma 4 26B A4B");
    expect(shortModelName("Free Models Router")).toBe("Free Models Router");
    expect(openRouterLabel({ name: "Google: Gemma 4 31B (free)", context_length: 262144, tools: true })).toBe("Gemma 4 31B · 262k");
    expect(openRouterLabel({ name: "DeepSeek: R1 0528 (free)", context_length: 163840, tools: false })).toBe("R1 0528 · 164k · no tools");
    expect(openRouterLabel({ name: "X: Y (free)", context_length: null, tools: true })).toBe("Y");
  });

  it("knows which live models cannot call tools", () => {
    const live = [
      { alias: "openrouter/a/b", id: "a/b", name: "A", context_length: 1000, tools: false, free: true },
      { alias: "openrouter/c/d", id: "c/d", name: "C", context_length: 1000, tools: true, free: true },
    ];
    expect(lacksToolCalling("openrouter/a/b", live)).toBe(true);
    expect(lacksToolCalling("openrouter/c/d", live)).toBe(false);
    expect(lacksToolCalling("openrouter/x/y", live)).toBe(false);
    expect(lacksToolCalling("openrouter/a/b", undefined)).toBe(false);
  });
});
