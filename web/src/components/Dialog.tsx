import type { ReactNode } from "react";

import { Icon } from "./Icon";

export function Dialog({
  children,
  description,
  kicker = "새 증거",
  onClose,
  title,
}: {
  children: ReactNode;
  description: string;
  /** Overridden for dialogs that are not about producing evidence. */
  kicker?: string;
  onClose: () => void;
  title: string;
}) {
  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        aria-labelledby="dialog-title"
        aria-modal="true"
        className="dialog"
        role="dialog"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="dialog-header">
          <div>
            <span className="kicker">{kicker}</span>
            <h2 id="dialog-title">{title}</h2>
            <p>{description}</p>
          </div>
          <button aria-label="대화상자 닫기" className="icon-button" type="button" onClick={onClose}>
            <Icon name="close" />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}
