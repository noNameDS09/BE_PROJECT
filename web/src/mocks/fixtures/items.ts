/**
 * Mock EvalItems. Illustrative only: values follow the companies' reported figures as best we
 * know, but nothing here is verified gold data. Real items come from `loupe datasets` / Loupe-Gold.
 */
import type { EvalItem, Kind } from "../../api/types";
import { COMPANY_BY_ID, SHORT_NAME } from "./config";

type ItemInit = Partial<EvalItem> & Pick<EvalItem, "item_id" | "question" | "kind">;

export function makeItem(init: ItemInit): EvalItem {
  const dataset = init.dataset ?? init.item_id.split(":")[0] ?? "unknown";
  const company = init.companies?.[0];
  return {
    dataset,
    answer: null,
    answer_value: null,
    answer_unit: null,
    tolerance: 0.01,
    mode: "corpus",
    context: null,
    documents: [],
    evidence: [],
    companies: [],
    fiscal_year: null,
    turns: [],
    expected_tools: [],
    expected_intents: [],
    split: company ? (COMPANY_BY_ID[company]?.split ?? null) : null,
    category: null,
    meta: {},
    ...init,
  };
}

/** Reported values in USD millions: [ticker, concept label, XBRL concept, { fiscal year: value }]. */
export const VALUE_TABLE: [string, string, string, Record<number, number>][] = [
  ["AMD", "net revenue", "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", { 2022: 23601, 2023: 22680, 2024: 25785 }],
  ["PEP", "net revenue", "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", { 2023: 91471, 2024: 91854 }],
  ["JNJ", "sales to customers", "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", { 2023: 85159, 2024: 88821 }],
  ["ADBE", "total revenue", "us-gaap:Revenues", { 2023: 19409, 2024: 21505 }],
  ["BBY", "revenue", "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", { 2024: 43452, 2025: 41528 }],
  ["ULTA", "net sales", "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", { 2023: 11207, 2024: 11296 }],
  ["VZ", "total operating revenue", "us-gaap:Revenues", { 2023: 133974, 2024: 134788 }],
  ["PFE", "total revenues", "us-gaap:Revenues", { 2023: 58496, 2024: 63627 }],
  ["UNH", "total revenues", "us-gaap:Revenues", { 2023: 371622, 2024: 400278 }],
  ["CVS", "total revenues", "us-gaap:Revenues", { 2023: 357776, 2024: 372809 }],
  ["BA", "total revenues", "us-gaap:Revenues", { 2023: 77794, 2024: 66517 }],
  ["AXP", "total revenues net of interest expense", "us-gaap:Revenues", { 2023: 60515, 2024: 65949 }],
  ["MGM", "total revenues", "us-gaap:Revenues", { 2023: 16164, 2024: 17241 }],
  ["JPM", "net income", "us-gaap:NetIncomeLoss", { 2023: 49552, 2024: 58471 }],
];

function usdMillions(v: number): string {
  return `$${v.toLocaleString("en-US")} million`;
}

function generatedNumericItems(): EvalItem[] {
  const out: EvalItem[] = [];
  for (const [ticker, label, concept, values] of VALUE_TABLE) {
    const name = SHORT_NAME[ticker] ?? ticker;
    const years = Object.keys(values).map(Number).sort();
    for (const fy of years) {
      const v = values[fy] as number;
      out.push(
        makeItem({
          item_id: `loupe-gold:num-${ticker}-${concept.split(":")[1]}-FY${fy}`,
          question: `What was ${name}'s ${label} for fiscal ${fy}?`,
          kind: "numeric",
          answer: usdMillions(v),
          answer_value: v * 1e6,
          answer_unit: "USD",
          companies: [ticker],
          fiscal_year: fy,
          category: "metric_lookup",
          expected_tools: ["get_facts"],
          expected_intents: ["metric_lookup"],
          meta: { concept, builder: "xbrl-lookup-v1", verified_by: ["xbrl_match", "second_model"], audit: null },
        }),
      );
    }
    if (years.length >= 2) {
      const a = years[years.length - 2] as number;
      const b = years[years.length - 1] as number;
      const va = values[a] as number;
      const vb = values[b] as number;
      const growth = ((vb - va) / va) * 100;
      out.push(
        makeItem({
          item_id: `loupe-gold:growth-${ticker}-FY${b}`,
          question: `By what percentage did ${name}'s ${label} change from fiscal ${a} to fiscal ${b}?`,
          kind: "numeric",
          answer: `${growth >= 0 ? "+" : ""}${growth.toFixed(1)}% (${usdMillions(va)} → ${usdMillions(vb)})`,
          answer_value: Number(growth.toFixed(2)),
          answer_unit: "%",
          tolerance: 0.02,
          companies: [ticker],
          fiscal_year: b,
          category: "growth",
          expected_tools: ["get_facts", "calc"],
          expected_intents: ["metric_lookup", "growth"],
          meta: { concept, builder: "xbrl-growth-v1", verified_by: ["xbrl_match", "calc_check"], audit: null },
        }),
      );
    }
  }
  return out;
}

const AMD_10K_24 = "AMD_10-K_0000002488-25-000012";
const UNH_8K_105 = "UNH_8-K_0000731766-24-000021";
const SHAK_8K_206 = "SHAK_8-K_0001620533-25-000008";

const HANDWRITTEN: EvalItem[] = [
  // ---- scenario items (have hand-written answers per arm in mocks/scenarios.ts)
  makeItem({
    item_id: "loupe-gold:amd-rev-growth-FY2024",
    question: "What was AMD's total net revenue in fiscal 2024, and how did it change from fiscal 2023?",
    kind: "numeric",
    answer: "$25,785 million, up 13.7% from $22,680 million in fiscal 2023",
    answer_value: 25785e6,
    answer_unit: "USD",
    companies: ["AMD"],
    fiscal_year: 2024,
    category: "growth",
    expected_tools: ["get_facts", "calc", "search_filings"],
    expected_intents: ["metric_lookup", "growth", "explain"],
    evidence: [
      { doc_id: AMD_10K_24, page: null, text: "Net revenue for 2024 was $25.8 billion, an increase of 14% compared to 2023 net revenue of $22.7 billion.", accession: "0000002488-25-000012", item: "7" },
    ],
    meta: { builder: "manual", verified_by: ["xbrl_match", "quote_match", "second_model"], audit: "pass" },
  }),
  makeItem({
    item_id: "loupe-gold:trick-SHAK-ch11",
    question: "How much did Shake Shack write down after its Chapter 11 filing in 2024?",
    kind: "refusal",
    answer: "False premise. Shake Shack did not file for Chapter 11 in FY2023–25: no 8-K Item 1.03 exists for the company. Its 8-Ks in the window report impairments (Item 2.06) and non-reliance (Item 4.02).",
    companies: ["SHAK"],
    fiscal_year: 2024,
    category: "false_premise",
    expected_tools: ["list_events"],
    expected_intents: ["event_lookup"],
    evidence: [{ doc_id: SHAK_8K_206, page: null, text: null, accession: "0001620533-25-000008", item: "2.06" }],
    meta: { builder: "trick-v1", premise: "invented_event", verified_by: ["event_table_absent"], audit: "pass" },
  }),
  makeItem({
    item_id: "loupe-gold:event-UNH-1.05",
    question: "What did UnitedHealth disclose about the Change Healthcare cyberattack, and when did it happen?",
    kind: "event",
    answer: "8-K Item 1.05 (Material Cybersecurity Incident): on February 21, 2024 a cyber threat actor gained access to some of Change Healthcare's IT systems; the company isolated the affected systems and engaged law enforcement and security experts.",
    companies: ["UNH"],
    fiscal_year: 2024,
    category: "cyber_incident",
    expected_tools: ["list_events", "search_filings"],
    expected_intents: ["event_lookup"],
    evidence: [
      { doc_id: UNH_8K_105, page: null, text: "On February 21, 2024, UnitedHealth Group Incorporated identified a suspected nation-state associated cyber security threat actor had gained access to some of the Change Healthcare information technology systems.", accession: "0000731766-24-000021", item: "1.05" },
    ],
    meta: { builder: "event-8k-v1", event_type: "cybersecurity_incident", label_source: "8k_item", quality_score: 5, audit: "pass" },
  }),
  // ---- other Loupe-Gold items
  makeItem({
    item_id: "loupe-gold:trick-PEP-restatement",
    question: "Why did PepsiCo restate its fiscal 2023 financial statements?",
    kind: "refusal",
    answer: "False premise. PepsiCo filed no 8-K Item 4.02 (non-reliance) in FY2023–25 and did not restate its fiscal 2023 statements.",
    companies: ["PEP"],
    fiscal_year: 2023,
    category: "false_premise",
    expected_tools: ["list_events"],
    expected_intents: ["event_lookup"],
    meta: { builder: "trick-v1", premise: "invented_event", audit: null },
  }),
  makeItem({
    item_id: "loupe-gold:event-ADM-4.02",
    question: "What did Archer-Daniels-Midland disclose under 8-K Item 4.02 in 2024?",
    kind: "event",
    answer: "Non-reliance on previously issued financial statements: certain intersegment transactions, mainly involving the Nutrition segment, had not been recorded at amounts approximating market, so segment information was corrected.",
    companies: ["ADM"],
    fiscal_year: 2024,
    category: "non_reliance",
    expected_tools: ["list_events", "search_filings"],
    expected_intents: ["event_lookup"],
    meta: { builder: "event-8k-v1", event_type: "non_reliance", label_source: "8k_item", quality_score: 4, audit: null },
  }),
  makeItem({
    item_id: "loupe-gold:compare-KR-CMP-current-ratio",
    question: "Compare Kroger's and Compass Minerals' current ratios at the end of fiscal 2024.",
    kind: "plan",
    companies: ["KR", "CMP"],
    fiscal_year: 2024,
    category: "comparison",
    expected_tools: ["get_facts", "get_facts", "calc", "calc", "compare"],
    expected_intents: ["ratio", "compare"],
    meta: { builder: "plan-v1", audit: null },
  }),
  makeItem({
    item_id: "loupe-gold:text-RIG-impairment",
    question: "Why did Transocean record impairment charges on drilling rigs in 2024?",
    kind: "text",
    answer: "It classified certain older floaters as held for sale (or decided to retire them) and wrote their carrying amounts down to fair value less costs to sell.",
    companies: ["RIG"],
    fiscal_year: 2024,
    category: "explain",
    expected_tools: ["search_filings"],
    expected_intents: ["explain"],
    meta: { builder: "manual", audit: null },
  }),
  makeItem({
    item_id: "loupe-gold:conv-AMD-01",
    question: "And how much did it grow the following year, in percent?",
    kind: "numeric",
    answer: "13.7%",
    answer_value: 13.69,
    answer_unit: "%",
    tolerance: 0.02,
    companies: ["AMD"],
    fiscal_year: 2024,
    turns: ["What was AMD's net revenue in fiscal 2023?"],
    category: "multi_turn",
    expected_tools: ["get_facts", "calc"],
    expected_intents: ["growth"],
    meta: { builder: "conv-v1", audit: null },
  }),
  // ---- FinanceBench-style items (bring-your-own-docs mode)
  makeItem({
    item_id: "financebench:fb_amd_quick_ratio_fy22",
    dataset: "financebench",
    question: "Does AMD have a reasonably healthy liquidity profile based on its quick ratio for FY22? If the quick ratio is not relevant to measure liquidity, please state that and explain why.",
    kind: "text",
    answer: "Yes. The quick ratio is about 1.57, calculated as (cash and cash equivalents + short-term investments + accounts receivable, net + receivables from related parties) / current liabilities.",
    mode: "docs",
    documents: [{ doc_id: "AMD_2022_10K", title: "AMD 2022 10-K", text: null, path: "financebench/pdfs/AMD_2022_10K.pdf" }],
    evidence: [{ doc_id: "AMD_2022_10K", page: 56, text: "Consolidated Balance Sheets — Current assets: Cash and cash equivalents $4,835 …", accession: null, item: "8" }],
    companies: ["AMD"],
    fiscal_year: 2022,
    category: "metrics-generated",
    meta: { question_type: "metrics-generated", question_reasoning: "Numerical reasoning OR Logical reasoning" },
  }),
  makeItem({
    item_id: "financebench:fb_mmm_capex_fy22",
    dataset: "financebench",
    question: "Is 3M a capital-intensive business based on FY2022 data?",
    kind: "text",
    answer: "No. 3M manages capex and fixed assets efficiently: capex/revenue about 5.1%, fixed assets/total assets about 20%, return on assets about 12.4%.",
    mode: "docs",
    documents: [{ doc_id: "3M_2022_10K", title: "3M 2022 10-K", text: null, path: "financebench/pdfs/3M_2022_10K.pdf" }],
    evidence: [{ doc_id: "3M_2022_10K", page: 47, text: "Purchases of property, plant and equipment (PP&E) (1,749)", accession: null, item: "8" }],
    companies: ["MMM"],
    fiscal_year: 2022,
    category: "metrics-generated",
    meta: { question_type: "metrics-generated", question_reasoning: "Numerical reasoning" },
  }),
  ...(
    [
      ["JNJ", 2023, 85159, "total sales to customers"],
      ["PEP", 2023, 91471, "net revenue"],
      ["ADBE", 2023, 19409, "total revenue"],
      ["VZ", 2023, 133974, "total operating revenues"],
      ["PFE", 2023, 58496, "total revenues"],
      ["CVS", 2023, 357776, "total revenues"],
      ["AMD", 2023, 22680, "net revenue"],
    ] as [string, number, number, string][]
  ).map(([t, fy, v, label]) =>
    makeItem({
      item_id: `financebench:fb_${t.toLowerCase()}_rev_fy${String(fy).slice(2)}`,
      dataset: "financebench",
      question: `What is the FY${fy} ${label} for ${SHORT_NAME[t]}? Answer in USD millions. Base your answer on the income statement.`,
      kind: "numeric" as Kind,
      answer: usdMillions(v),
      answer_value: v * 1e6,
      answer_unit: "USD",
      mode: "docs" as const,
      documents: [{ doc_id: `${t}_${fy}_10K`, title: `${SHORT_NAME[t]} ${fy} 10-K`, text: null, path: `financebench/pdfs/${t}_${fy}_10K.pdf` }],
      evidence: [{ doc_id: `${t}_${fy}_10K`, page: null, text: null, accession: null, item: "8" }],
      companies: [t],
      fiscal_year: fy,
      category: "domain-relevant",
      meta: { question_type: "domain-relevant", question_reasoning: "Information extraction" },
    }),
  ),
  // ---- FailSafeQA-style items (inline context)
  makeItem({
    item_id: "failsafeqa:fsq-0112-missing",
    dataset: "failsafeqa",
    question: "What was the company's operating margin in the most recent quarter?",
    kind: "refusal",
    answer: "The provided context does not contain operating income or revenue for the most recent quarter, so the margin cannot be computed.",
    mode: "context",
    context: "Item 1A. Risk Factors. Our business could be adversely affected by changes in consumer spending, inflationary pressures and supply-chain disruptions. We operate in highly competitive markets …",
    category: "missing_context",
    meta: { perturbation: "irrelevant_context" },
  }),
  makeItem({
    item_id: "failsafeqa:fsq-0112-base",
    dataset: "failsafeqa",
    question: "What was the company's operating margin in the most recent quarter?",
    kind: "text",
    answer: "About 18.4% (operating income $1,512 million on net revenue $8,217 million).",
    mode: "context",
    context: "Net revenue for the quarter was $8,217 million … Operating income was $1,512 million, compared with $1,288 million in the prior-year quarter …",
    category: "baseline",
    meta: { perturbation: "none" },
  }),
  makeItem({
    item_id: "failsafeqa:fsq-0298-typo",
    dataset: "failsafeqa",
    question: "Waht was the yoy chnage in net incmoe?",
    kind: "text",
    answer: "Net income rose 9.6% year over year, from $2.18 billion to $2.39 billion.",
    mode: "context",
    context: "Net income was $2.39 billion, compared with $2.18 billion in the prior year …",
    category: "misspelled_query",
    meta: { perturbation: "misspelling" },
  }),
  // ---- FinDER-style retrieval items
  makeItem({
    item_id: "finder:fd-7781",
    dataset: "finder",
    question: "AMD data center segment growth drivers 2024",
    kind: "retrieval",
    companies: ["AMD"],
    fiscal_year: 2024,
    evidence: [
      { doc_id: AMD_10K_24, page: null, text: "Data Center segment net revenue was $12.6 billion, an increase of 94% compared to 2023, primarily driven by the strong ramp of AMD Instinct GPU shipments and growth in AMD EPYC CPU sales.", accession: "0000002488-25-000012", item: "7" },
    ],
    category: "segment",
    meta: { annotator: "expert" },
  }),
  makeItem({
    item_id: "finder:fd-8020",
    dataset: "finder",
    question: "UNH change healthcare cyber attack business disruption",
    kind: "retrieval",
    companies: ["UNH"],
    fiscal_year: 2024,
    evidence: [{ doc_id: UNH_8K_105, page: null, text: "Upon detection of this outside threat, the Company proactively isolated the impacted systems from other connecting parties …", accession: "0000731766-24-000021", item: "1.05" }],
    category: "risk",
    meta: { annotator: "expert" },
  }),
];

export const ITEMS: EvalItem[] = [...HANDWRITTEN, ...generatedNumericItems()];

export const ITEM_BY_ID: Record<string, EvalItem> = Object.fromEntries(ITEMS.map((i) => [i.item_id, i]));

export function datasetNames(): string[] {
  return [...new Set(ITEMS.map((i) => i.dataset))];
}
