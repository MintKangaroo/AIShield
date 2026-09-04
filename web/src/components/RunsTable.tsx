import { formatDate, formatPercent } from "../format";
import type { BaselineRunRecord, DatasetRecord, ModelVersionRecord } from "../types";
import { Icon } from "./Icon";

export function RunsTable({
  datasets,
  models,
  onSelect,
  runs,
  selectedId,
  totalCount,
}: {
  datasets: DatasetRecord[];
  models: ModelVersionRecord[];
  onSelect: (id: string) => void;
  runs: BaselineRunRecord[];
  selectedId?: string;
  /** Total ledger size, so a truncated preview keeps stable BL-### labels. */
  totalCount?: number;
}) {
  if (!runs.length) {
    return (
      <div className="empty-panel">
        <span className="empty-icon">
          <Icon name="beaker" size={22} />
        </span>
        <h3>아직 베이스라인 증거가 없습니다</h3>
        <p>데이터셋과 모델을 적재한 뒤 첫 결정론적 평가를 실행하세요.</p>
      </div>
    );
  }

  const ledgerSize = totalCount ?? runs.length;
  return (
    <div className="runs-table">
      <div className="runs-head">
        <span>실행</span>
        <span>대상</span>
        <span>clean 정확도</span>
        <span>지연</span>
        <span>증거</span>
        <span />
      </div>
      {runs.map((run, index) => {
        const dataset = datasets.find((item) => item.id === run.dataset_id);
        const model = models.find((item) => item.id === run.model_version_id);
        return (
          <button
            className={`run-row ${selectedId === run.id ? "selected" : ""}`}
            key={run.id}
            type="button"
            onClick={() => onSelect(run.id)}
          >
            <span className="run-id">
              <b>BL-{String(ledgerSize - index).padStart(3, "0")}</b>
              <small>{formatDate(run.created_at)}</small>
            </span>
            <span className="target-cell">
              <b>{model?.architecture ?? "알 수 없는 모델"}</b>
              <small>
                {dataset?.name.toUpperCase() ?? "알 수 없는 데이터셋"} / {dataset?.split ?? "—"}
              </small>
            </span>
            <strong className="metric-value">{formatPercent(run.metrics.clean_accuracy)}</strong>
            <span className="mono">{run.metrics.latency.mean_ms_per_sample.toFixed(2)} ms</span>
            <span className="sealed">
              <Icon name="check" size={13} /> 봉인됨
            </span>
            <Icon name="chevron" size={16} />
          </button>
        );
      })}
    </div>
  );
}
