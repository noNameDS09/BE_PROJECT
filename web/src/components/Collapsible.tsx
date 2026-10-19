import type { ReactNode } from "react";
import { Icon } from "./Icon";

/** A native <details> section with a styled summary. */
export function Collapsible({
  title,
  meta,
  defaultOpen = false,
  children,
}: {
  title: ReactNode;
  meta?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  return (
    <details className="collapsible" open={defaultOpen}>
      <summary>
        <Icon name="chevron" size={12} className="chev" />
        {title}
        {meta !== undefined && <span className="faint" style={{ fontWeight: 500 }}>{meta}</span>}
      </summary>
      <div className="collapsible-body">{children}</div>
    </details>
  );
}
