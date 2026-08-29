import type { ReactNode } from "react";

import { Icon } from "./Icon";

export function Dialog({
  children,
  description,
  onClose,
  title,
}: {
  children: ReactNode;
  description: string;
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
            <span className="kicker">New evidence</span>
            <h2 id="dialog-title">{title}</h2>
            <p>{description}</p>
          </div>
          <button aria-label="Close dialog" className="icon-button" type="button" onClick={onClose}>
            <Icon name="close" />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}
