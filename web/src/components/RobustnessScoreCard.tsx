import { formatPercent } from "../format";
import type { RobustnessScore } from "../types";
import { Icon } from "./Icon";

export function RobustnessScoreCard({
  busy,
  onCalculate,
  score,
  selectedCount,
}: {
  busy: boolean;
  onCalculate: () => void;
  score: RobustnessScore | null;
  selectedCount: number;
}) {
  return (
    <section className="panel score-panel">
      <div className="panel-heading">
        <div>
          <span className="kicker">Transparent aggregate</span>
          <h3>Robustness score</h3>
        </div>
        <button
          className="button secondary compact"
          disabled={busy || selectedCount < 1}
          type="button"
          onClick={onCalculate}
        >
          <Icon name="gauge" size={15} />
          {busy ? "Aggregating…" : `Score ${selectedCount} selected`}
        </button>
      </div>

      {score ? (
        <>
          <div className="score-summary">
            <div
              className="score-ring compact"
              style={{ "--score": score.score } as React.CSSProperties}
            >
              <div>
                <strong>{formatPercent(score.score)}</strong>
                <span>mean robust acc.</span>
              </div>
            </div>
            <dl className="score-facts">
              <div>
                <dt>Formula</dt>
                <dd className="mono">{score.formula_version}</dd>
              </div>
              <div>
                <dt>Evidence coverage</dt>
                <dd>{formatPercent(score.evidence_coverage)}</dd>
              </div>
              <div>
                <dt>Attacks used</dt>
                <dd>{score.attacks_used.map((item) => item.toUpperCase()).join(", ")}</dd>
              </div>
              <div>
                <dt>Runs aggregated</dt>
                <dd>{score.attack_run_ids.length}</dd>
              </div>
            </dl>
          </div>
          {score.warnings.map((warning) => (
            <div className="attack-warning" key={warning}>
              <Icon name="activity" size={16} />
              <span>
                <strong>Interpretation limit</strong>
                {warning}
              </span>
            </div>
          ))}
        </>
      ) : (
        <p className="score-hint">
          Select attack runs that share one model and dataset, then aggregate them. The score never
          replaces the raw per-attack metrics, and incomplete algorithm coverage is reported
          instead of hidden.
        </p>
      )}
    </section>
  );
}
