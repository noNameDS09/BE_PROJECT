import { describe, expect, it } from "vitest";
import type { RunResult } from "../api/types";
import { toMessages } from "./ChatPage";

describe("chat history", () => {
  it("skips a failed answer instead of crashing on the next message", () => {
    const failed: RunResult = {
      run_id: "r1", arm: "loupe", model: "mistral-small", question: "q", answer: null,
      tokens: 0, latency_ms: 0, cost_usd: 0, gold: null, error: "RateLimitError",
    };
    const msgs = toMessages([
      { role: "user", content: "first" },
      { role: "assistant", result: failed },
      { role: "user", content: "second" },
    ]);
    expect(msgs).toEqual([
      { role: "user", content: "first" },
      { role: "user", content: "second" },
    ]);
  });
});
