/**
 * Mock filing store for the citation viewer (/api/documents/{doc_id}). Each document holds the
 * cited passages at their character offsets plus surrounding section text, so the viewer can
 * show the span in context. Passage wording is illustrative, modelled on the filings.
 */

export interface MockPassage {
  start: number;
  text: string;
}

export interface MockDocument {
  doc_id: string;
  company_id: string;
  form: string;
  period_end: string | null;
  url: string;
  before: string;
  after: string;
  passages: MockPassage[];
}

export const AMD_10K = {
  id: "AMD_10-K_0000002488-25-000012",
  url: "https://www.sec.gov/Archives/edgar/data/2488/000000248825000012/amd-20241228.htm",
  revenuePassage:
    "Net revenue for 2024 was $25.8 billion, an increase of 14% compared to 2023 net revenue of $22.7 billion. The increase in net revenue was primarily driven by a 94% increase in Data Center segment revenue, driven by the strong ramp of AMD Instinct GPU shipments and growth in AMD EPYC CPU sales, and a 52% increase in Client segment revenue driven by strong demand for AMD Ryzen processors, partially offset by a 58% decrease in Gaming segment revenue and a 33% decrease in Embedded segment revenue.",
  revenueStart: 48211,
};

export const UNH_8K = {
  id: "UNH_8-K_0000731766-24-000021",
  url: "https://www.sec.gov/Archives/edgar/data/731766/000073176624000021/unh-20240221.htm",
  incidentPassage:
    "On February 21, 2024, UnitedHealth Group Incorporated (the “Company”) identified a suspected nation-state associated cyber security threat actor had gained access to some of the Change Healthcare information technology systems. Immediately upon detection of this outside threat, the Company proactively isolated the impacted systems from other connecting parties in the interest of protecting our partners and patients, to contain, assess and remediate the incident.",
  incidentStart: 1184,
};

export const UNH_10K = {
  id: "UNH_10-K_0000731766-25-000063",
  url: "https://www.sec.gov/Archives/edgar/data/731766/000073176625000063/unh-20241231.htm",
  costPassage:
    "The Change Healthcare cyberattack resulted in business disruption impacts and direct response costs, including costs to restore and secure the affected systems, medical record review, notifications and the temporary funding assistance provided to care providers affected by the disruption.",
  costStart: 211508,
};

export const SHAK_8K = {
  id: "SHAK_8-K_0001620533-25-000008",
  url: "https://www.sec.gov/Archives/edgar/data/1620533/000162053325000008/shak-8k.htm",
  impairmentPassage:
    "Item 2.06 Material Impairments. Following a review of its Shack portfolio, the Company concluded that a material charge for impairment is required for certain underperforming Shacks, which the Company intends to close.",
  impairmentStart: 902,
};

const DOCS: MockDocument[] = [
  {
    doc_id: AMD_10K.id,
    company_id: "AMD",
    form: "10-K",
    period_end: "2024-12-28",
    url: AMD_10K.url,
    before:
      "ITEM 7. MANAGEMENT’S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS\n\nThe following discussion should be read in conjunction with the December 28, 2024 Consolidated Financial Statements and related notes, which are included in Part II, Item 8 of this Annual Report on Form 10-K. Our fiscal year ends on the last Saturday of December.\n\nOverview\n\n",
    after:
      "\n\nGross margin was 49%, compared to 46% in 2023. Operating income was $1.9 billion, compared to $401 million in 2023. The increase in operating income was primarily driven by higher revenue and gross margin, partially offset by higher operating expenses. Net income was $1.6 billion, compared to $854 million in 2023.\n\nCritical Accounting Estimates",
    passages: [{ start: AMD_10K.revenueStart, text: AMD_10K.revenuePassage }],
  },
  {
    doc_id: UNH_8K.id,
    company_id: "UNH",
    form: "8-K",
    period_end: "2024-02-21",
    url: UNH_8K.url,
    before: "UNITED STATES SECURITIES AND EXCHANGE COMMISSION\nWashington, D.C. 20549\n\nFORM 8-K\n\nCURRENT REPORT\n\nItem 1.05 Material Cybersecurity Incidents.\n\n",
    after:
      "\n\nThe Company is working with law enforcement and has retained leading security experts. The network interruption is specific to Change Healthcare and all other systems across the Company are operational. As of the date of this report, the Company has not determined the incident is reasonably likely to materially impact the Company’s financial condition or results of operations.",
    passages: [{ start: UNH_8K.incidentStart, text: UNH_8K.incidentPassage }],
  },
  {
    doc_id: UNH_10K.id,
    company_id: "UNH",
    form: "10-K",
    period_end: "2024-12-31",
    url: UNH_10K.url,
    before: "ITEM 7. MANAGEMENT’S DISCUSSION AND ANALYSIS\n\nCyberattack\n\nIn February 2024, the Company experienced a cyberattack on its Change Healthcare subsidiary. ",
    after: " These impacts are reflected in the consolidated results of the Optum Insight segment and in medical costs.\n\nResults Summary",
    passages: [{ start: UNH_10K.costStart, text: UNH_10K.costPassage }],
  },
  {
    doc_id: SHAK_8K.id,
    company_id: "SHAK",
    form: "8-K",
    period_end: "2025-02-13",
    url: SHAK_8K.url,
    before: "FORM 8-K\n\nCURRENT REPORT PURSUANT TO SECTION 13 OR 15(d) OF THE SECURITIES EXCHANGE ACT OF 1934\n\nShake Shack Inc.\n\n",
    after:
      " The Company expects to record the related charges in its fiscal fourth quarter and will provide further detail in its Annual Report on Form 10-K.\n\nItem 9.01 Financial Statements and Exhibits.",
    passages: [{ start: SHAK_8K.impairmentStart, text: SHAK_8K.impairmentPassage }],
  },
];

export const DOC_BY_ID: Record<string, MockDocument> = Object.fromEntries(DOCS.map((d) => [d.doc_id, d]));
