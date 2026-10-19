import type { ReactNode } from "react";

export interface Option {
  value: string;
  label: string;
}

/** A labelled <select> used in filter bars. Empty value means "all". */
export function FilterSelect({
  label,
  value,
  onChange,
  options,
  allLabel = "All",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: Option[];
  allLabel?: string | null;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <select className="select" value={value} onChange={(e) => onChange(e.target.value)}>
        {allLabel !== null && <option value="">{allLabel}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function FilterBar({ children }: { children: ReactNode }) {
  return <div className="filters">{children}</div>;
}

export function SortHeader<K extends string>({
  label,
  k,
  sort,
  onSort,
  right,
}: {
  label: string;
  k: K;
  sort: { key: K; dir: "asc" | "desc" };
  onSort: (k: K) => void;
  right?: boolean;
}) {
  const active = sort.key === k;
  return (
    <th
      className={`sortable${right ? " r" : ""}`}
      onClick={() => onSort(k)}
      aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
    >
      {label}
      {active && <span className="arrow">{sort.dir === "asc" ? "↑" : "↓"}</span>}
    </th>
  );
}
