import { describe, expect, it } from "vitest";
import { ApiError, buildQuery, createHttpClient } from "./client";

describe("buildQuery", () => {
  it("skips empty values and encodes the rest", () => {
    expect(buildQuery({ dataset: "loupe-gold", split: "", model: undefined, q: "a b", limit: 50 })).toBe("?dataset=loupe-gold&q=a+b&limit=50");
    expect(buildQuery({})).toBe("");
  });
});

function fakeFetch(status: number, body: unknown, calls: { url: string; init?: RequestInit }[] = []): typeof fetch {
  return (async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    return new Response(typeof body === "string" ? body : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  }) as unknown as typeof fetch;
}

describe("http client", () => {
  it("builds URLs under the base and posts JSON", async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    const client = createHttpClient("/api/", fakeFetch(200, { results: [] }, calls));
    await client.compare({ question: "q", item_id: null, configs: [{ arm: "b0", model: "groq-llama-70b" }] });
    await client.document("AMD_10-K_x", { start: 10, end: 20 });
    await client.datasetItem("financebench", "financebench:fb 1");
    expect(calls[0]?.url).toBe("/api/compare");
    expect(calls[0]?.init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0]?.init?.body))).toMatchObject({ question: "q", configs: [{ arm: "b0" }] });
    expect(calls[1]?.url).toBe("/api/documents/AMD_10-K_x?start=10&end=20");
    expect(calls[2]?.url).toBe("/api/datasets/financebench/items/financebench%3Afb%201");
  });

  it("turns {detail} error bodies into ApiError", async () => {
    const client = createHttpClient("/api", fakeFetch(404, { detail: "Unknown dataset: nope" }));
    await expect(client.datasetItems("nope")).rejects.toMatchObject({ status: 404, detail: "Unknown dataset: nope" });
  });

  it("flattens FastAPI validation errors", async () => {
    const client = createHttpClient("/api", fakeFetch(422, { detail: [{ loc: ["body", "configs"], msg: "too many configs" }] }));
    const err = await client.compare({ question: "q", item_id: null, configs: [] }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).detail).toBe("too many configs");
  });

  it("reports network failures with status 0", async () => {
    const failing = (async () => {
      throw new TypeError("Failed to fetch");
    }) as unknown as typeof fetch;
    const err = await createHttpClient("/api", failing)
      .health()
      .catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(0);
  });
});
