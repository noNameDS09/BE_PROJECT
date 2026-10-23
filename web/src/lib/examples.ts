export interface DemoQuestion {
  id: string;
  /** About three words, e.g. "Number + growth". */
  title: string;
  question: string;
  /** The capability the question demonstrates. */
  shows: string;
  /** One sentence telling a viewer what to notice when comparing methods. */
  lookFor: string;
}

/** Ten demo questions offered on Compare and Chat, each showing one capability. */
export const DEMO_QUESTIONS: DemoQuestion[] = [
  {
    id: "number-growth",
    title: "Number + growth",
    question: "What was AMD's total net revenue in fiscal 2024, and how did it change from fiscal 2023?",
    shows: "Exact XBRL lookup and a computed change",
    lookFor: "The plain LLM guesses; Loupe's numbers carry citations that open the 10-K.",
  },
  {
    id: "three-company-compare",
    title: "Three-company compare",
    question:
      "Compare the fiscal 2024 revenue and net income of PepsiCo, Kroger and Archer-Daniels-Midland. Which had the highest net margin?",
    shows: "Multi-company comparison plus calculation (multi-intent)",
    lookFor: "Every number is cited, and the margin is computed by the calculator, not by the model.",
  },
  {
    id: "trend-chart",
    title: "Trend chart",
    question: "Chart Boeing's annual revenue from fiscal 2021 to 2024 and explain the drop in 2024.",
    shows: "Chart from XBRL plus narrative from filings",
    lookFor: "A chart built from cited facts; the explanation quotes the 10-K.",
  },
  {
    id: "forecast",
    title: "Forecast",
    question: "Forecast Ulta Beauty's revenue for the next two fiscal years, with an uncertainty range.",
    shows: "Statistical forecast with a backtest against a naive baseline",
    lookFor: "An 80% range and the backtest error, rather than a confident single number.",
  },
  {
    id: "distress-score",
    title: "Distress score",
    question: "How did Diebold Nixdorf's Altman Z'' distress score change from fiscal 2022 to 2024, and which 8-K events explain it?",
    shows: "Distress score plus 8-K risk events",
    lookFor: "It moves from the distress zone to the grey zone, and bankruptcy-related 8-K items are cited.",
  },
  {
    id: "cyber-incident",
    title: "Cyber incident",
    question: "What did UnitedHealth disclose about the Change Healthcare cyberattack, and when did it file the 8-K?",
    shows: "8-K event lookup (Item 1.05)",
    lookFor: "The filing date and item code come from the event table, with a link.",
  },
  {
    id: "balance-sheet-ratio",
    title: "Balance-sheet ratio",
    question: "What was Verizon's long-term debt to equity ratio at the end of Q2 2025?",
    shows: "A quarter-specific ratio from two XBRL facts",
    lookFor: "Both inputs are cited and the ratio (about 1.19) is computed by code.",
  },
  {
    id: "risk-narrative",
    title: "Risk narrative",
    question: "What risks does Transocean highlight about offshore drilling demand in its latest 10-K?",
    shows: "Retrieval from Item 1A risk factors",
    lookFor: "Quotes that open the exact passage in the filing.",
  },
  {
    id: "false-premise",
    title: "False premise",
    question: "Why did Shake Shack file for Chapter 11 bankruptcy in 2024?",
    shows: "False-premise detection",
    lookFor: "Loupe says no such filing exists, while plain models often invent reasons.",
  },
  {
    id: "future-period",
    title: "Future period",
    question: "What was Johnson & Johnson's revenue in fiscal 2027?",
    shows: "Refusing a period that has not happened",
    lookFor: "Loupe abstains and says what is missing; ungrounded models may make up a figure.",
  },
];

/** Just the question texts, in demo order. */
export const EXAMPLE_QUESTIONS = DEMO_QUESTIONS.map((d) => d.question);

/** The demo whose question is exactly `question` (after trimming), if any. */
export function findDemo(question: string): DemoQuestion | undefined {
  const q = question.trim();
  return q ? DEMO_QUESTIONS.find((d) => d.question === q) : undefined;
}

/** Arms a demo runs side by side on Compare: closed book, a generic agent, and Loupe. */
export const DEMO_ARMS = ["b0", "react", "loupe"] as const;

/** The dataset an item belongs to: item ids are "<dataset>:<native id>". */
export function datasetOf(itemId: string): string {
  const i = itemId.indexOf(":");
  return i > 0 ? itemId.slice(0, i) : itemId;
}
