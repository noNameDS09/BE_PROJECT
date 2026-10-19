/**
 * Mock implementation of the API (VITE_MOCK=1). Behaves like the backend described in
 * docs/api.md: same shapes, same filters, same errors, plus a small artificial delay.
 */
import { ApiError, type ApiClient } from "../api/client";
import { MAX_COMPARE_CONFIGS, type ConfigResponse, type DatasetInfo, type Kind } from "../api/types";
import { sleep } from "./builders";
import { ARMS, COMPANIES, MODELS } from "./fixtures/config";
import { DOC_BY_ID } from "./fixtures/documents";
import { ITEMS, ITEM_BY_ID, datasetNames } from "./fixtures/items";
import { leaderboardRows, runRows, stageSteps } from "./fixtures/results";
import { buildRun } from "./scenarios";

export { SUGGESTED_QUESTIONS } from "./scenarios";

export interface MockOptions {
  /** Base latency per call in ms; runs take ~3× longer. 0 disables delays (tests). */
  delayMs?: number;
}

function datasets(): DatasetInfo[] {
  return datasetNames().map((name) => {
    const items = ITEMS.filter((i) => i.dataset === name);
    const kinds = [...new Set(items.map((i) => i.kind))] as Kind[];
    return { name, items: items.length, kinds };
  });
}

export function createMockClient(opts: MockOptions = {}): ApiClient {
  const base = opts.delayMs ?? 350;
  const wait = (factor = 1) => sleep(base * factor * (0.7 + Math.random() * 0.6));
  let counter = 0;

  return {
    async health() {
      await wait(0.3);
      return { ok: true, index: "c1200o150-bge-small", models_with_keys: MODELS.filter((m) => m.available).length };
    },

    async config(): Promise<ConfigResponse> {
      await wait(0.5);
      return { arms: ARMS, models: MODELS, datasets: datasets(), companies: COMPANIES };
    },

    async run(body) {
      if (!body.question && !body.item_id) throw new ApiError(422, "question or item_id is required");
      if (body.item_id && !ITEM_BY_ID[body.item_id]) throw new ApiError(404, `Unknown item_id: ${body.item_id}`);
      await wait(3);
      return buildRun({ question: body.question || null, itemId: body.item_id, arm: body.arm, model: body.model, salt: String(++counter) });
    },

    async compare(body) {
      if (!body.configs.length) throw new ApiError(422, "configs must contain at least one { arm, model }");
      if (body.configs.length > MAX_COMPARE_CONFIGS) throw new ApiError(422, `At most ${MAX_COMPARE_CONFIGS} configs per comparison`);
      if (!body.question?.trim() && !body.item_id) throw new ApiError(422, "question or item_id is required");
      if (body.item_id && !ITEM_BY_ID[body.item_id]) throw new ApiError(404, `Unknown item_id: ${body.item_id}`);
      const unknownArm = body.configs.find((c) => !ARMS.some((a) => a.name === c.arm));
      if (unknownArm) throw new ApiError(422, `Unknown arm: ${unknownArm.arm}`);
      await wait(4);
      const salt = String(++counter);
      return {
        results: body.configs.map((c) =>
          buildRun({ question: body.item_id ? null : (body.question ?? null), itemId: body.item_id, arm: c.arm, model: c.model, salt }),
        ),
      };
    },

    async datasetItems(name, query = {}) {
      await wait();
      if (!datasetNames().includes(name)) throw new ApiError(404, `Unknown dataset: ${name}`);
      const q = query.q?.trim().toLowerCase();
      const filtered = ITEMS.filter((i) => i.dataset === name)
        .filter((i) => !query.split || i.split === query.split)
        .filter((i) => !query.kind || i.kind === query.kind)
        .filter(
          (i) =>
            !q ||
            i.question.toLowerCase().includes(q) ||
            i.item_id.toLowerCase().includes(q) ||
            i.companies.some((c) => c.toLowerCase() === q),
        );
      const offset = Math.max(0, query.offset ?? 0);
      const limit = Math.min(200, Math.max(1, query.limit ?? 50));
      return { total: filtered.length, items: filtered.slice(offset, offset + limit) };
    },

    async datasetItem(name, itemId) {
      await wait(0.5);
      const item = ITEM_BY_ID[itemId];
      if (!item || item.dataset !== name) throw new ApiError(404, `Unknown item ${itemId} in dataset ${name}`);
      return item;
    },

    async leaderboard(query = {}) {
      await wait();
      return { rows: leaderboardRows(query) };
    },

    async stages(query = {}) {
      await wait();
      return { steps: stageSteps(query) };
    },

    async runs(query = {}) {
      await wait();
      return { rows: runRows(query) };
    },

    async document(docId, query = {}) {
      await wait(0.6);
      const doc = DOC_BY_ID[docId];
      if (!doc) throw new ApiError(404, `Document not found in the mock store: ${docId}`);
      const context = query.context ?? 600;
      const start = query.start ?? null;
      const passage = doc.passages.find((p) => start === null || (start >= p.start && start < p.start + p.text.length)) ?? doc.passages[0];
      if (!passage) throw new ApiError(404, `No text for ${docId}`);
      const before = doc.before.slice(-context);
      const after = doc.after.slice(0, context);
      const hlStart = before.length + Math.max(0, (start ?? passage.start) - passage.start);
      const end = query.end ?? passage.start + passage.text.length;
      const hlEnd = before.length + Math.min(passage.text.length, end - passage.start);
      return {
        doc_id: doc.doc_id,
        company_id: doc.company_id,
        form: doc.form,
        period_end: doc.period_end,
        url: doc.url,
        text: before + passage.text + after,
        highlight: [hlStart, hlEnd],
      };
    },

    async chat(body) {
      const last = [...body.messages].reverse().find((m) => m.role === "user");
      if (!last?.content.trim()) throw new ApiError(422, "messages must end with a user message");
      await wait(3);
      return buildRun({ question: last.content, itemId: null, arm: "loupe", model: body.model, salt: String(++counter) });
    },
  };
}
