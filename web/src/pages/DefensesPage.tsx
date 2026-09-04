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
            <span className="kicker">전 / 후 / 적응</span>
            <h3>{defenses.length} defense evaluations</h3>
          </div>
          <button className="button secondary compact" type="button" onClick={onOpenDefense}>
            <Icon name="shield" size={15} /> 방어 실행
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
              <h3>짝지은 방어 증거</h3>
            </div>
            <span className="mono faint">{formatDate(selectedDefense.created_at)}</span>
          </div>

          <div className="defense-compare">
            {(
              [
                {
                  label: "clean 정확도",
                  before: metrics.clean_accuracy_before,
                  after: metrics.clean_accuracy_after,
                  hint: "변형 없는 입력에서 방어의 비용",
                },
                {
                  label: "robust 정확도",
                  before: metrics.robust_accuracy_before,
                  after: metrics.robust_accuracy_after,
                  hint: "공격 하에서 방어의 이득",
                },
                {
                  label: "공격 성공률",
                  before: metrics.attack_success_rate_before,
                  after: metrics.attack_success_rate_after,
                  hint: "낮을수록 좋음; clean-correct 샘플 기준",
                },
              ] as const
            ).map((row) => (
              <article key={row.label}>
                <h4>{row.label}</h4>
                <div className="defense-bars">
                  <div>
                    <span>
                      <small>전</small>
                      <b>{formatPercent(row.before)}</b>
                    </span>
                    <i>
                      <em style={{ width: `${row.before * 100}%` }} />
                    </i>
                  </div>
                  <div className="after">
                    <span>
                      <small>후</small>
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
                : "평평한 적응 그래디언트는 강건성이 아니라 그래디언트 마스킹을 뜻합니다."}
            </span>
          </div>

          {selectedDefense.warnings.map((warning) => (
            <div className="attack-warning" key={warning}>
              <Icon name="activity" size={16} />
              <span>
                <strong>평가 경고</strong>
                {warning}
              </span>
            </div>
          ))}
        </section>
      )}

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="kicker">블랙박스 증거</span>
            <h3>{transfers.length} surrogate-to-target transfers</h3>
          </div>
          <button className="button secondary compact" type="button" onClick={onOpenTransfer}>
            <Icon name="transfer" size={15} /> 전이 실행
          </button>
        </div>
        <TransferTable datasets={datasets} models={models} transfers={transfers} />
      </section>
    </div>
  );
}
