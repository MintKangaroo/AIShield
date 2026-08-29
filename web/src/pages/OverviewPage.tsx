import { ConfusionMatrix } from "../components/ConfusionMatrix";
import { Icon } from "../components/Icon";
import { RunsTable } from "../components/RunsTable";
import { formatPercent, shortHash } from "../format";
import type { ApiState } from "../hooks/useRegistry";
import type {
  AttackRunRecord,
  BaselineRunRecord,
  BaselineVerification,
  DatasetRecord,
  ModelVersionRecord,
} from "../types";

export function OverviewPage({
  apiState,
  artifactCount,
  baselines,
  busy,
  datasets,
  models,
  onOpenAttack,
  onOpenBaseline,
  onSelectRun,
  onStartDemo,
  onViewAllRuns,
  selectedAttack,
  selectedDataset,
  selectedRun,
  verification,
}: {
  apiState: ApiState;
  artifactCount: number;
  baselines: BaselineRunRecord[];
  busy: boolean;
  datasets: DatasetRecord[];
  models: ModelVersionRecord[];
  onOpenAttack: () => void;
  onOpenBaseline: () => void;
  onSelectRun: (id: string) => void;
  onStartDemo: () => void;
  onViewAllRuns: () => void;
  selectedAttack: AttackRunRecord | null;
  selectedDataset: DatasetRecord | undefined;
  selectedRun: BaselineRunRecord | null;
  verification: BaselineVerification | undefined;
}) {
  return (
    <div className="page-content">
      <section className="hero">
        <div className="hero-copy">
          <span className="hero-badge">
            <Icon name="shield" size={14} /> Reproducible by design
          </span>
          <h2>
            Evidence before
            <br />
            <em>confidence.</em>
          </h2>
          <p>
            Establish a trusted clean baseline before you claim robustness. AIShield binds every
            result to the exact model, data, seed, runtime and generated artifacts.
          </p>
          <div className="hero-actions">
            <button className="button primary" type="button" onClick={onOpenBaseline}>
              <Icon name="play" size={16} /> Run baseline
            </button>
            {models.length > 0 && datasets.length > 0 && (
              <button className="button secondary" type="button" onClick={onOpenAttack}>
                <Icon name="spark" size={16} /> Run bounded attack
              </button>
            )}
            {!baselines.length && (
              <button
                className="button secondary"
                disabled={busy || apiState !== "ready"}
                type="button"
                onClick={onStartDemo}
              >
                <Icon name="spark" size={16} />
                {busy ? "Preparing demo…" : "Launch zero-download demo"}
              </button>
            )}
          </div>
        </div>
        <div className="hero-visual" aria-hidden="true">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="shield-core">
            <Icon name="shield" size={48} />
          </div>
          <span className="signal signal-one">MODEL / SHA-256</span>
          <span className="signal signal-two">DATA / MANIFEST</span>
          <span className="signal signal-three">RUN / SEALED</span>
        </div>
      </section>

      <section className="stat-grid" aria-label="Workspace metrics">
        <article>
          <span className="stat-icon lime">
            <Icon name="activity" />
          </span>
          <div>
            <small>Latest clean accuracy</small>
            <strong>
              {selectedRun ? formatPercent(selectedRun.metrics.clean_accuracy) : "—"}
            </strong>
            <span>
              {selectedRun ? `${selectedRun.metrics.evaluated_samples} samples` : "No run yet"}
            </span>
          </div>
        </article>
        <article>
          <span className="stat-icon violet">
            <Icon name="fingerprint" />
          </span>
          <div>
            <small>Reproducibility</small>
            <strong>{verification ? (verification.reproducible ? "PASS" : "FAIL") : "READY"}</strong>
            <span>
              {verification ? `${verification.checks.length} checks` : "Exact rerun available"}
            </span>
          </div>
        </article>
        <article>
          <span className="stat-icon blue">
            <Icon name="shield" />
          </span>
          <div>
            <small>Latest robust accuracy</small>
            <strong>
              {selectedAttack ? formatPercent(selectedAttack.metrics.robust_accuracy) : "—"}
            </strong>
            <span>
              {selectedAttack
                ? `${selectedAttack.config.algorithm.toUpperCase()} · ε ${Math.round(selectedAttack.config.epsilon * 255)}/255`
                : "No attack evaluated"}
            </span>
          </div>
        </article>
        <article>
          <span className="stat-icon amber">
            <Icon name="archive" />
          </span>
          <div>
            <small>Evidence artifacts</small>
            <strong>{artifactCount}</strong>
            <span>Hash-verified outputs</span>
          </div>
        </article>
      </section>

      <div className="dashboard-grid">
        <section className="panel performance-panel">
          <div className="panel-heading">
            <div>
              <span className="kicker">Model behavior</span>
              <h3>Class-level recall</h3>
            </div>
            <span className="panel-chip">
              {selectedDataset?.name.toUpperCase() ?? "NO DATA"} · CLEAN
            </span>
          </div>
          <div className="class-chart">
            {(selectedRun?.metrics.per_class ?? []).slice(0, 10).map((metric) => (
              <div className="class-bar" key={metric.class_index}>
                <span>{metric.class_index}</span>
                <div>
                  <i style={{ height: `${Math.max(3, metric.recall * 100)}%` }} />
                </div>
                <small>{Math.round(metric.recall * 100)}</small>
              </div>
            ))}
            {!selectedRun &&
              Array.from({ length: 10 }, (_, index) => (
                <div className="class-bar placeholder" key={index}>
                  <span>{index}</span>
                  <div>
                    <i style={{ height: `${18 + ((index * 17) % 58)}%` }} />
                  </div>
                  <small>—</small>
                </div>
              ))}
          </div>
          <div className="chart-footer">
            <span>
              <i className="legend-dot clean" /> Recall by true class
            </span>
            <span>
              Mean loss <b>{selectedRun?.metrics.mean_loss.toFixed(4) ?? "—"}</b>
            </span>
          </div>
        </section>

        <section className="panel matrix-panel">
          <div className="panel-heading">
            <div>
              <span className="kicker">Prediction map</span>
              <h3>Confusion matrix</h3>
            </div>
            {selectedRun && (
              <span className="mono faint">{shortHash(selectedRun.metrics.prediction_sha256)}</span>
            )}
          </div>
          <ConfusionMatrix run={selectedRun} />
        </section>
      </div>

      <section className="panel recent-panel">
        <div className="panel-heading">
          <div>
            <span className="kicker">Immutable ledger</span>
            <h3>Recent baseline runs</h3>
          </div>
          <button className="text-button" type="button" onClick={onViewAllRuns}>
            View all runs <Icon name="arrow" size={15} />
          </button>
        </div>
        <RunsTable
          datasets={datasets}
          models={models}
          runs={baselines.slice(0, 4)}
          selectedId={selectedRun?.id}
          totalCount={baselines.length}
          onSelect={onSelectRun}
        />
      </section>
    </div>
  );
}
