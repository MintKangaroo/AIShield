import { Icon } from "../components/Icon";
import { formatDate, formatPercent } from "../format";
import type { DatasetRecord, RemoteAttackRunRecord } from "../types";

export function RemoteAttacksPage({
  datasets,
  onOpenRemoteAttack,
  runs,
}: {
  datasets: DatasetRecord[];
  onOpenRemoteAttack: () => void;
  runs: RemoteAttackRunRecord[];
}) {
  return (
    <div className="page-content">
      <section className="registry-summary">
        <div>
          <span className="summary-icon">
            <Icon name="transfer" size={26} />
          </span>
          <div>
            <h2>Black-box attacks on deployed models</h2>
            <p>
              Query an authorized remote classifier with images and read back only its scores — no
              weights, no gradient. The host must be allowlisted and each run explicitly authorized.
            </p>
          </div>
        </div>
        <button className="button secondary compact" type="button" onClick={onOpenRemoteAttack}>
          <Icon name="spark" size={15} /> Run black-box attack
        </button>
      </section>

      <section className="panel">
        {runs.length ? (
          <div className="attack-table">
            <div className="attack-head remote-head">
              <span>Target</span>
              <span>Probe</span>
              <span>Clean</span>
              <span>Robust</span>
              <span>Success</span>
              <span>Queries</span>
              <span>Bound</span>
            </div>
            {runs.map((run) => {
              const dataset = datasets.find((item) => item.id === run.dataset_id);
              return (
                <div className="attack-row remote-row" key={run.id}>
                  <span className="attack-name">
                    <i>SQUARE</i>
                    <span>
                      <b>{run.target_host}</b>
                      <small>{formatDate(run.created_at)}</small>
                    </span>
                  </span>
                  <span className="target-cell">
                    <b>{dataset?.name.toUpperCase() ?? "Unknown"}</b>
                    <small>{run.metrics.evaluated_samples} samples</small>
                  </span>
                  <span className="mono">{formatPercent(run.metrics.clean_accuracy)}</span>
                  <strong className="robust-value">
                    {formatPercent(run.metrics.robust_accuracy)}
                  </strong>
                  <span className="mono">{formatPercent(run.metrics.attack_success_rate)}</span>
                  <span className="mono">{run.metrics.total_queries.toLocaleString()}</span>
                  <span className="bound-chip">
                    ε {Math.round(run.config.epsilon * 255)}/255
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="empty-panel">
            <span className="empty-icon transfer">
              <Icon name="transfer" size={22} />
            </span>
            <h3>No remote attacks yet</h3>
            <p>
              Point AIShield at an image classifier you are authorized to test. Set
              <code> AISHIELD_ATTACK_TARGETS_ALLOWLIST</code> on the server first — an empty
              allowlist refuses every target.
            </p>
            <button className="button primary compact" type="button" onClick={onOpenRemoteAttack}>
              Configure a target
            </button>
          </div>
        )}
      </section>

      {runs[0]?.warnings.length ? (
        <div className="attack-warning">
          <Icon name="activity" size={16} />
          <span>
            <strong>Interpretation</strong>
            {runs[0].warnings[0]}
          </span>
        </div>
      ) : null}
    </div>
  );
}
