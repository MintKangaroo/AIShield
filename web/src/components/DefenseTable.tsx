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
        <h3>아직 방어 증거가 없습니다</h3>
        <p>
          비트 심도 전처리 방어를 실행해 동일한 샘플 집단에서 전·후·적응 지표를 비교하세요.
        </p>
      </div>
    );
  }

  return (
    <div className="defense-table">
      <div className="defense-head">
        <span>방어</span>
        <span>대상</span>
        <span>robust 전</span>
        <span>robust 후</span>
        <span>Δ</span>
        <span>적응</span>
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
              <b>{model?.architecture ?? "알 수 없는 모델"}</b>
              <small>
                {dataset?.name.toUpperCase() ?? "알 수 없는 데이터셋"} ·{" "}
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
              title="전처리 방어를 통과한 적응 공격의 그래디언트 상태"
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
