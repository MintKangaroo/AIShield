import { useEffect, useState } from "react";

import { compareAttacks, compareBaselines } from "../compare";
import { ComparisonView } from "../components/ComparisonView";
import { Icon } from "../components/Icon";
import { formatDate } from "../format";
import type {
  AttackRunRecord,
  BaselineRunRecord,
  DatasetRecord,
  ModelVersionRecord,
} from "../types";

type Kind = "baseline" | "attack";

export function ComparePage({
  attacks,
  baselines,
  datasets,
  models,
}: {
  attacks: AttackRunRecord[];
  baselines: BaselineRunRecord[];
  datasets: DatasetRecord[];
  models: ModelVersionRecord[];
}) {
  const [kind, setKind] = useState<Kind>("baseline");
  const runs: Array<{ id: string; created_at: string }> =
    kind === "baseline" ? baselines : attacks;
  const [leftId, setLeftId] = useState("");
  const [rightId, setRightId] = useState("");

  // Default to the two most recent runs of the selected kind.
  useEffect(() => {
    setLeftId(runs[0]?.id ?? "");
    setRightId(runs[1]?.id ?? runs[0]?.id ?? "");
  }, [kind, runs.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const comparison = (() => {
    if (kind === "baseline") {
      const a = baselines.find((r) => r.id === leftId);
      const b = baselines.find((r) => r.id === rightId);
      return a && b ? compareBaselines(a, b, datasets, models) : null;
    }
    const a = attacks.find((r) => r.id === leftId);
    const b = attacks.find((r) => r.id === rightId);
    return a && b ? compareAttacks(a, b, datasets, models) : null;
  })();

  function label(run: { id: string; created_at: string }, index: number) {
    const prefix = kind === "baseline" ? "BL" : "AT";
    return `${prefix}-${String(runs.length - index).padStart(3, "0")} · ${formatDate(run.created_at)}`;
  }

  return (
    <div className="page-content">
      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="kicker">실행 간</span>
            <h3>두 실행 비교</h3>
          </div>
          <div className="attack-picker" role="group" aria-label="실행 종류">
            {(["baseline", "attack"] as const).map((item) => (
              <button
                className={kind === item ? "active" : ""}
                key={item}
                type="button"
                onClick={() => setKind(item)}
              >
                <span>{item === "baseline" ? "Baselines" : "Attacks"}</span>
              </button>
            ))}
          </div>
        </div>

        {runs.length < 2 ? (
          <div className="empty-panel">
            <span className="empty-icon">
              <Icon name="activity" size={22} />
            </span>
            <h3>비교하려면 실행이 2개 필요합니다</h3>
            <p>Run at least two {kind === "baseline" ? "baselines" : "attacks"} first.</p>
          </div>
        ) : (
          <>
            <div className="form-row two compare-pickers">
              <label>
                <span>실행 A</span>
                <select value={leftId} onChange={(event) => setLeftId(event.target.value)}>
                  {runs.map((run, index) => (
                    <option key={run.id} value={run.id}>
                      {label(run, index)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>실행 B</span>
                <select value={rightId} onChange={(event) => setRightId(event.target.value)}>
                  {runs.map((run, index) => (
                    <option key={run.id} value={run.id}>
                      {label(run, index)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {comparison && <ComparisonView comparison={comparison} />}
          </>
        )}
      </section>
    </div>
  );
}
