import type { CSSProperties } from "react";

import { api } from "../api";
import { Icon } from "../components/Icon";
import { RunsTable } from "../components/RunsTable";
import { formatDate, formatPercent, shortHash } from "../format";
import type {
  BaselineRunRecord,
  BaselineVerification,
  DatasetRecord,
  ModelVersionRecord,
} from "../types";

export function RunsPage({
  baselines,
  busy,
  datasets,
  models,
  onOpenBaseline,
  onSelectRun,
  onVerify,
  selectedDataset,
  selectedModel,
  selectedRun,
  verification,
}: {
  baselines: BaselineRunRecord[];
  busy: boolean;
  datasets: DatasetRecord[];
  models: ModelVersionRecord[];
  onOpenBaseline: () => void;
  onSelectRun: (id: string) => void;
  onVerify: (run: BaselineRunRecord) => void;
  selectedDataset: DatasetRecord | undefined;
  selectedModel: ModelVersionRecord | undefined;
  selectedRun: BaselineRunRecord | null;
  verification: BaselineVerification | undefined;
}) {
  return (
    <div className="page-content split-layout">
      <section className="panel runs-panel">
        <div className="panel-heading">
          <div>
            <span className="kicker">All evidence</span>
            <h3>{baselines.length} completed baselines</h3>
          </div>
          <button className="button secondary compact" type="button" onClick={onOpenBaseline}>
            <Icon name="plus" size={15} /> New run
          </button>
        </div>
        <RunsTable
          datasets={datasets}
          models={models}
          runs={baselines}
          selectedId={selectedRun?.id}
          onSelect={onSelectRun}
        />
      </section>

      <aside className="panel inspector">
        {selectedRun ? (
          <>
            <div className="inspector-top">
              <span className="sealed large">
                <Icon name="check" size={14} /> Evidence sealed
              </span>
              <span className="mono faint">{formatDate(selectedRun.created_at)}</span>
            </div>
            <h2>{selectedModel?.architecture ?? "Model baseline"}</h2>
            <p>
              {selectedDataset?.name.toUpperCase()} / {selectedDataset?.split} · seed{" "}
              {selectedRun.config.seed}
            </p>
            <div
              className="score-ring"
              style={{ "--score": selectedRun.metrics.clean_accuracy } as CSSProperties}
            >
              <div>
                <strong>{formatPercent(selectedRun.metrics.clean_accuracy)}</strong>
                <span>clean accuracy</span>
              </div>
            </div>
            <div className="metric-pairs">
              <span>
                <small>Mean loss</small>
                <b>{selectedRun.metrics.mean_loss.toFixed(4)}</b>
              </span>
              <span>
                <small>Latency / sample</small>
                <b>{selectedRun.metrics.latency.mean_ms_per_sample.toFixed(2)} ms</b>
              </span>
              <span>
                <small>Samples</small>
                <b>{selectedRun.metrics.evaluated_samples.toLocaleString()}</b>
              </span>
              <span>
                <small>Artifacts</small>
                <b>{selectedRun.artifacts.length}</b>
              </span>
            </div>
            <div className="hash-stack">
              <span>
                <small>Model state</small>
                <code>{shortHash(selectedRun.model_state_sha256)}</code>
              </span>
              <span>
                <small>Dataset manifest</small>
                <code>{shortHash(selectedRun.dataset_manifest_sha256)}</code>
              </span>
              <span>
                <small>Predictions</small>
                <code>{shortHash(selectedRun.metrics.prediction_sha256)}</code>
              </span>
            </div>
            {verification && (
              <div className={`verification-result ${verification.reproducible ? "pass" : "fail"}`}>
                <Icon name={verification.reproducible ? "check" : "close"} />
                <span>
                  <strong>
                    {verification.reproducible ? "Reproduction passed" : "Mismatch detected"}
                  </strong>
                  {verification.checks.filter((check) => check.passed).length}/
                  {verification.checks.length} deterministic checks passed
                </span>
              </div>
            )}
            <button
              className="button primary full"
              disabled={busy}
              type="button"
              onClick={() => onVerify(selectedRun)}
            >
              <Icon name="refresh" size={16} />
              {busy ? "Replaying exact run…" : "Verify exact rerun"}
            </button>
            <a
              className="button secondary full"
              download={`experiment-${selectedRun.id}.json`}
              href={api.experimentUrl(selectedRun.id)}
            >
              <Icon name="download" size={16} />
              Export experiment envelope
            </a>
            <small className="inspector-footnote">
              Wall-clock latency is recorded but excluded from pass/fail.
            </small>
          </>
        ) : (
          <div className="empty-panel compact-empty">
            <Icon name="activity" size={24} />
            <h3>Select a baseline</h3>
            <p>Run evidence will appear here.</p>
          </div>
        )}
      </aside>
    </div>
  );
}
