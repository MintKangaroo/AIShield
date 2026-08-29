import { Icon } from "../components/Icon";
import { JobsTable } from "../components/JobsTable";
import { formatDate, formatPercent } from "../format";
import type { JobRecord, ModelVersionRecord, TrainingRunRecord } from "../types";

export function JobsPage({
  hasPendingJob,
  jobs,
  models,
  onOpenTraining,
  training,
}: {
  hasPendingJob: boolean;
  jobs: JobRecord[];
  models: ModelVersionRecord[];
  onOpenTraining: () => void;
  training: TrainingRunRecord[];
}) {
  return (
    <div className="page-content">
      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="kicker">Bounded worker queue</span>
            <h3>{jobs.length} background jobs</h3>
          </div>
          {hasPendingJob && (
            <span className="live-chip">
              <i />
              Live
            </span>
          )}
          <button className="button secondary compact" type="button" onClick={onOpenTraining}>
            <Icon name="plus" size={15} /> Queue training
          </button>
        </div>
        <JobsTable jobs={jobs} />
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="kicker">Hardened checkpoints</span>
            <h3>{training.length} training runs</h3>
          </div>
        </div>
        {training.length ? (
          <div className="training-table">
            <div className="training-head">
              <span>Run</span>
              <span>Strategy</span>
              <span>Clean acc.</span>
              <span>Robust acc.</span>
              <span>Final loss</span>
              <span>Checkpoint</span>
            </div>
            {training.map((run, index) => {
              const trained = models.find((item) => item.id === run.trained_model_version_id);
              return (
                <div className="training-row" key={run.id}>
                  <span className="run-id">
                    <b>TN-{String(training.length - index).padStart(3, "0")}</b>
                    <small>{formatDate(run.created_at)}</small>
                  </span>
                  <span className="target-cell">
                    <b>{run.config.strategy === "trades" ? "TRADES" : "Adversarial"}</b>
                    <small>
                      {run.metrics.epochs_completed} epochs · ε{" "}
                      {Math.round(run.config.epsilon * 255)}/255
                    </small>
                  </span>
                  <span className="mono">{formatPercent(run.metrics.final_clean_accuracy)}</span>
                  <strong className="robust-value">
                    {formatPercent(run.metrics.final_robust_accuracy)}
                  </strong>
                  <span className="mono">{run.metrics.final_training_loss.toFixed(4)}</span>
                  <span className="target-cell">
                    <b>{trained?.name ?? "Trained model"}</b>
                    <small className="mono">{run.model_state_sha256.slice(0, 12)}</small>
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="empty-panel">
            <span className="empty-icon">
              <Icon name="layers" size={22} />
            </span>
            <h3>No hardened checkpoints yet</h3>
            <p>
              Adversarial training and TRADES copy the source model and store the result as hashed
              evidence.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
