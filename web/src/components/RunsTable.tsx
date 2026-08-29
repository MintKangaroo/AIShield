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
        <h3>No baseline evidence yet</h3>
        <p>Load a dataset and model, then run the first deterministic evaluation.</p>
      </div>
    );
  }

  const ledgerSize = totalCount ?? runs.length;
  return (
    <div className="runs-table">
      <div className="runs-head">
        <span>Run</span>
        <span>Target</span>
        <span>Clean acc.</span>
        <span>Latency</span>
        <span>Evidence</span>
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
              <b>{model?.architecture ?? "Unknown model"}</b>
              <small>
                {dataset?.name.toUpperCase() ?? "Unknown dataset"} / {dataset?.split ?? "—"}
              </small>
            </span>
            <strong className="metric-value">{formatPercent(run.metrics.clean_accuracy)}</strong>
            <span className="mono">{run.metrics.latency.mean_ms_per_sample.toFixed(2)} ms</span>
            <span className="sealed">
              <Icon name="check" size={13} /> Sealed
            </span>
            <Icon name="chevron" size={16} />
          </button>
        );
      })}
    </div>
  );
}
