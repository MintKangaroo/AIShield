import { formatDate, formatDelta, formatPercent } from "../format";
import type { DatasetRecord, DefenseRunRecord, ModelVersionRecord } from "../types";
import { Icon } from "./Icon";

export function DefenseTable({
  datasets,
  defenses,
  models,
  onSelect,
  selectedId,
}: {
  datasets: DatasetRecord[];
  defenses: DefenseRunRecord[];
  models: ModelVersionRecord[];
  onSelect: (id: string) => void;
  selectedId?: string;
}) {
  if (!defenses.length) {
    return (
      <div className="empty-panel">
        <span className="empty-icon defense">
          <Icon name="shield" size={22} />
        </span>
        <h3>No defense evidence yet</h3>
        <p>
          Run a bit-depth preprocessing defense to compare before, after, and adaptive metrics on
          one identical sample population.
        </p>
      </div>
    );
  }

  return (
    <div className="defense-table">
      <div className="defense-head">
        <span>Defense</span>
        <span>Target</span>
        <span>Robust before</span>
        <span>Robust after</span>
        <span>Δ</span>
        <span>Adaptive</span>
        <span />
      </div>
      {defenses.map((defense, index) => {
        const dataset = datasets.find((item) => item.id === defense.dataset_id);
        const model = models.find((item) => item.id === defense.model_version_id);
        const before = defense.metrics.robust_accuracy_before;
        const after = defense.metrics.robust_accuracy_after;
        return (
          <button
            className={`defense-row ${selectedId === defense.id ? "selected" : ""}`}
            key={defense.id}
            type="button"
            onClick={() => onSelect(defense.id)}
          >
            <span className="attack-name">
              <i>{defense.defense.bit_depth}-BIT</i>
              <span>
                <b>DF-{String(defenses.length - index).padStart(3, "0")}</b>
                <small>{formatDate(defense.created_at)}</small>
              </span>
            </span>
            <span className="target-cell">
              <b>{model?.architecture ?? "Unknown model"}</b>
              <small>
                {dataset?.name.toUpperCase() ?? "Unknown dataset"} ·{" "}
                {defense.attack_algorithm.toUpperCase()}
              </small>
            </span>
            <span className="mono">{formatPercent(before)}</span>
            <strong className="robust-value">{formatPercent(after)}</strong>
            <span className={`delta-chip ${after >= before ? "up" : "down"}`}>
              {formatDelta(before, after)}
            </span>
            <span
              className={`gradient-chip ${defense.metrics.adaptive_gradient_status}`}
              title="Adaptive attack gradient health through the preprocessing defense"
            >
              {defense.metrics.adaptive_gradient_status}
            </span>
            <Icon name="chevron" size={16} />
          </button>
        );
      })}
    </div>
  );
}
