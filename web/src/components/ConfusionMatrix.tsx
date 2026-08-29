import type { CSSProperties } from "react";

import type { BaselineRunRecord } from "../types";
import { Icon } from "./Icon";

export function ConfusionMatrix({ run }: { run: BaselineRunRecord | null }) {
  if (!run) {
    return (
      <div className="matrix-empty">
        <Icon name="grid" size={24} />
        <span>Run a baseline to generate the matrix</span>
      </div>
    );
  }

  const matrix = run.metrics.confusion_matrix;
  const maximum = Math.max(...matrix.flat(), 1);
  return (
    <div className="matrix-wrap">
      <div className="matrix-y-label">Actual class</div>
      <div
        aria-label="Confusion matrix"
        className="matrix"
        role="img"
        style={{ gridTemplateColumns: `repeat(${matrix.length}, minmax(0, 1fr))` }}
      >
        {matrix.flatMap((row, rowIndex) =>
          row.map((value, columnIndex) => (
            <span
              className="matrix-cell"
              key={`${rowIndex}-${columnIndex}`}
              title={`Actual ${rowIndex}, predicted ${columnIndex}: ${value}`}
              style={{ "--cell-strength": Math.max(0.08, value / maximum) } as CSSProperties}
            >
              {matrix.length <= 10 ? value : ""}
            </span>
          )),
        )}
      </div>
      <div className="matrix-x-label">Predicted class</div>
    </div>
  );
}
