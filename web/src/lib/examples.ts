/** Example questions offered on Compare and Chat (each has a hand-written mock fixture). */
export const EXAMPLE_QUESTIONS = [
  "What was AMD's total net revenue in fiscal 2024, and how did it change from fiscal 2023?",
  "How much did Shake Shack write down after its Chapter 11 filing in 2024?",
  "What did UnitedHealth disclose about the Change Healthcare cyberattack, and when did it happen?",
];

/** The dataset an item belongs to: item ids are "<dataset>:<native id>". */
export function datasetOf(itemId: string): string {
  const i = itemId.indexOf(":");
  return i > 0 ? itemId.slice(0, i) : itemId;
}
