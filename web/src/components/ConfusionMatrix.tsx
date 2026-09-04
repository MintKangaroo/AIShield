import type { CSSProperties } from "react";

import type { BaselineRunRecord } from "../types";
import { Icon } from "./Icon";

export function ConfusionMatrix({ run }: { run: BaselineRunRecord | null }) {
  if (!run) {
    return (
      <div className="matrix-empty">
        <Icon name="grid" size={24} />
        <span>행렬을 생성하려면 베이스라인을 실행하세요</span>
      </div>
    );
  }

  const matrix = run.metrics.confusion_matrix;
  const maximum = Math.max(...matrix.flat(), 1);
  return (
    <div className="matrix-wrap">
      <div className="matrix-y-label">실제 클래스</div>
      <div
        aria-label="혼동 행렬"
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
      <div className="matrix-x-label">예측 클래스</div>
    </div>
  );
}
