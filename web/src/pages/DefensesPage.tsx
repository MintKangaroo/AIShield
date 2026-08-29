import { DefenseTable } from "../components/DefenseTable";
import { Icon } from "../components/Icon";
import { TransferTable } from "../components/TransferTable";
import { formatDate, formatDelta, formatPercent } from "../format";
import type {
  DatasetRecord,
  DefenseRunRecord,
  ModelVersionRecord,
  TransferRunRecord,
} from "../types";

export function DefensesPage({
  datasets,
  defenses,
  models,
  onOpenDefense,
  onOpenTransfer,
  onSelectDefense,
  selectedDefense,
  transfers,
}: {
  datasets: DatasetRecord[];
  defenses: DefenseRunRecord[];
  models: ModelVersionRecord[];
  onOpenDefense: () => void;
  onOpenTransfer: () => void;
  onSelectDefense: (id: string) => void;
  selectedDefense: DefenseRunRecord | null;
  transfers: TransferRunRecord[];
}) {
  const metrics = selectedDefense?.metrics;
  return (
    <div className="page-content">
      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="kicker">Before / after / adaptive</span>
            <h3>{defenses.length} defense evaluations</h3>
          </div>
          <button className="button secondary compact" type="button" onClick={onOpenDefense}>
            <Icon name="shield" size={15} /> Run defense
          </button>
        </div>
        <DefenseTable
          datasets={datasets}
          defenses={defenses}
          models={models}
          selectedId={selectedDefense?.id}
          onSelect={onSelectDefense}
        />
      </section>

      {selectedDefense && metrics && (
        <section className="panel defense-detail">
          <div className="panel-heading">
            <div>
              <span className="kicker">
                {selectedDefense.defense.bit_depth}-bit quantization ·{" "}
                {selectedDefense.attack_algorithm.toUpperCase()}
              </span>
              <h3>Paired defense evidence</h3>
            </div>
            <span className="mono faint">{formatDate(selectedDefense.created_at)}</span>
          </div>

          <div className="defense-compare">
            {(
              [
                {
                  label: "Clean accuracy",
                  before: metrics.clean_accuracy_before,
                  after: metrics.clean_accuracy_after,
                  hint: "Cost of the defense on unperturbed inputs",
                },
                {
                  label: "Robust accuracy",
                  before: metrics.robust_accuracy_before,
                  after: metrics.robust_accuracy_after,
                  hint: "Benefit of the defense under attack",
                },
                {
                  label: "Attack success rate",
                  before: metrics.attack_success_rate_before,
                  after: metrics.attack_success_rate_after,
                  hint: "Lower is better; measured on clean-correct samples",
                },
              ] as const
            ).map((row) => (
              <article key={row.label}>
                <h4>{row.label}</h4>
                <div className="defense-bars">
                  <div>
                    <span>
                      <small>Before</small>
                      <b>{formatPercent(row.before)}</b>
                    </span>
                    <i>
                      <em style={{ width: `${row.before * 100}%` }} />
                    </i>
                  </div>
                  <div className="after">
                    <span>
                      <small>After</small>
                      <b>{formatPercent(row.after)}</b>
                    </span>
                    <i>
                      <em style={{ width: `${row.after * 100}%` }} />
                    </i>
                  </div>
                </div>
                <footer>
                  <span className={`delta-chip ${row.after >= row.before ? "up" : "down"}`}>
                    {formatDelta(row.before, row.after)}
                  </span>
                  <small>{row.hint}</small>
                </footer>
              </article>
            ))}
          </div>

          <div
            className={`verification-result ${metrics.adaptive_gradient_status === "healthy" ? "pass" : "fail"}`}
          >
            <Icon name={metrics.adaptive_gradient_status === "healthy" ? "check" : "close"} />
            <span>
              <strong>
                Adaptive gradient {metrics.adaptive_gradient_status === "healthy" ? "healthy" : "flat"}
              </strong>
              {metrics.adaptive_gradient_status === "healthy"
                ? `Measured over ${metrics.evaluated_samples} samples with a defense-aware attack.`
                : "A flat adaptive gradient indicates gradient masking, not robustness."}
            </span>
          </div>

          {selectedDefense.warnings.map((warning) => (
            <div className="attack-warning" key={warning}>
              <Icon name="activity" size={16} />
              <span>
                <strong>Evaluation warning</strong>
                {warning}
              </span>
            </div>
          ))}
        </section>
      )}

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="kicker">Black-box evidence</span>
            <h3>{transfers.length} surrogate-to-target transfers</h3>
          </div>
          <button className="button secondary compact" type="button" onClick={onOpenTransfer}>
            <Icon name="transfer" size={15} /> Run transfer
          </button>
        </div>
        <TransferTable datasets={datasets} models={models} transfers={transfers} />
      </section>
    </div>
  );
}
