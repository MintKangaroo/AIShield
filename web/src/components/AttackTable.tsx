import { formatDate, formatPercent } from "../format";
import type { AttackRunRecord, DatasetRecord, ModelVersionRecord } from "../types";
import { Icon } from "./Icon";

export function AttackTable({
  attacks,
  datasets,
  models,
  onSelect,
  onToggleScore,
  scoreSelection,
  selectedId,
}: {
  attacks: AttackRunRecord[];
  datasets: DatasetRecord[];
  models: ModelVersionRecord[];
  onSelect: (id: string) => void;
  /** Optional multi-select used to build a transparent robustness score. */
  onToggleScore?: (id: string) => void;
  scoreSelection?: ReadonlySet<string>;
  selectedId?: string;
}) {
  if (!attacks.length) {
    return (
      <div className="empty-panel">
        <span className="empty-icon attack">
          <Icon name="spark" size={22} />
        </span>
        <h3>No adversarial evaluations yet</h3>
        <p>Run FGSM for a fast signal or PGD for a stronger iterative check.</p>
      </div>
    );
  }

  return (
    <div className="attack-table">
      <div className="attack-head">
        <span>Attack</span>
        <span>Target</span>
        <span>Clean</span>
        <span>Robust</span>
        <span>Success</span>
        <span>Bound</span>
        <span />
      </div>
      {attacks.map((attack, index) => {
        const dataset = datasets.find((item) => item.id === attack.dataset_id);
        const model = models.find((item) => item.id === attack.model_version_id);
        const scoreSelected = scoreSelection?.has(attack.id) ?? false;
        return (
          <div className="attack-row-wrap" key={attack.id}>
            {onToggleScore && (
              <label className="score-pick" title="Include in robustness score">
                <input
                  aria-label={`Include ${attack.config.algorithm.toUpperCase()} run in robustness score`}
                  checked={scoreSelected}
                  type="checkbox"
                  onChange={() => onToggleScore(attack.id)}
                />
              </label>
            )}
            <button
              className={`attack-row ${selectedId === attack.id ? "selected" : ""}`}
              type="button"
              onClick={() => onSelect(attack.id)}
            >
              <span className="attack-name">
                <i>{attack.config.algorithm.toUpperCase()}</i>
                <span>
                  <b>AT-{String(attacks.length - index).padStart(3, "0")}</b>
                  <small>{formatDate(attack.created_at)}</small>
                </span>
              </span>
              <span className="target-cell">
                <b>{model?.architecture ?? "Unknown model"}</b>
                <small>{dataset?.name.toUpperCase() ?? "Unknown dataset"}</small>
              </span>
              <span className="mono">{formatPercent(attack.metrics.clean_accuracy)}</span>
              <strong className="robust-value">
                {formatPercent(attack.metrics.robust_accuracy)}
              </strong>
              <span className="mono">{formatPercent(attack.metrics.attack_success_rate)}</span>
              <span className="bound-chip">ε {Math.round(attack.config.epsilon * 255)}/255</span>
              <Icon name="chevron" size={16} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
