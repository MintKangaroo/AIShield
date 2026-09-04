import { AttackTable } from "../components/AttackTable";
import { Icon } from "../components/Icon";
import { RobustnessScoreCard } from "../components/RobustnessScoreCard";
import { StrengthCurve } from "../components/StrengthCurve";
import { formatDate, formatPercent } from "../format";
import type {
  AttackRunRecord,
  DatasetRecord,
  ModelVersionRecord,
  RobustnessScore,
} from "../types";

export function AttacksPage({
  attackDataset,
  attackModel,
  attacks,
  busy,
  curveRuns,
  datasets,
  models,
  onCalculateScore,
  onOpenAttack,
  onRunCurve,
  onSelectAttack,
  onToggleScore,
  score,
  scoreSelection,
  selectedAttack,
}: {
  attackDataset: DatasetRecord | undefined;
  attackModel: ModelVersionRecord | undefined;
  attacks: AttackRunRecord[];
  busy: boolean;
  curveRuns: AttackRunRecord[];
  datasets: DatasetRecord[];
  models: ModelVersionRecord[];
  onCalculateScore: () => void;
  onOpenAttack: () => void;
  onRunCurve: () => void;
  onSelectAttack: (id: string) => void;
  onToggleScore: (id: string) => void;
  score: RobustnessScore | null;
  scoreSelection: ReadonlySet<string>;
  selectedAttack: AttackRunRecord | null;
}) {
  return (
    <div className="page-content split-layout attack-layout">
      <section className="panel runs-panel">
        <div className="panel-heading">
          <div>
            <span className="kicker">짝지은 평가</span>
            <h3>{attacks.length} bounded attack runs</h3>
          </div>
          <button className="button secondary compact" type="button" onClick={onOpenAttack}>
            <Icon name="spark" size={15} /> 공격 실행
          </button>
          <button
            className="button ghost compact"
            disabled={!attackModel || !attackDataset || busy}
            type="button"
            onClick={onRunCurve}
          >
            <Icon name="activity" size={15} /> 강도 곡선
          </button>
        </div>
        <AttackTable
          attacks={attacks}
          datasets={datasets}
          models={models}
          scoreSelection={scoreSelection}
          selectedId={selectedAttack?.id}
          onSelect={onSelectAttack}
          onToggleScore={onToggleScore}
        />
      </section>

      <aside className="panel inspector attack-inspector">
        {selectedAttack ? (
          <>
            <div className="inspector-top">
              <span className="attack-status">
                <Icon
                  name={selectedAttack.metrics.gradient_status === "healthy" ? "check" : "close"}
                  size={13}
                />
                Gradient {selectedAttack.metrics.gradient_status}
              </span>
              <span className="mono faint">{formatDate(selectedAttack.created_at)}</span>
            </div>
            <span className="attack-title-badge">
              {selectedAttack.config.algorithm.toUpperCase()} ·{" "}
              {selectedAttack.config.norm === "l2" ? "L2" : "L∞"}
            </span>
            <h2>{attackModel?.architecture ?? "적대적 평가"}</h2>
            <p>
              {attackDataset?.name.toUpperCase()} / {attackDataset?.split} ·{" "}
              {selectedAttack.metrics.evaluated_samples} samples
            </p>

            <div className="accuracy-compare">
              <div>
                <span>
                  <small>clean 정확도</small>
                  <b>{formatPercent(selectedAttack.metrics.clean_accuracy)}</b>
                </span>
                <i>
                  <em style={{ width: `${selectedAttack.metrics.clean_accuracy * 100}%` }} />
                </i>
              </div>
              <div className="robust">
                <span>
                  <small>robust 정확도</small>
                  <b>{formatPercent(selectedAttack.metrics.robust_accuracy)}</b>
                </span>
                <i>
                  <em style={{ width: `${selectedAttack.metrics.robust_accuracy * 100}%` }} />
                </i>
              </div>
            </div>

            <div className="attack-success">
              <span>
                <Icon name="activity" />
                <small>공격 성공률</small>
              </span>
              <strong>{formatPercent(selectedAttack.metrics.attack_success_rate)}</strong>
              <p>
                {selectedAttack.metrics.successful_attacks} of{" "}
                {selectedAttack.metrics.clean_correct_samples} clean-correct samples changed to an
                incorrect prediction.
              </p>
            </div>

            <div className="metric-pairs attack-config">
              <span>
                <small>엡실론</small>
                <b>{(selectedAttack.config.epsilon * 255).toFixed(1)} / 255</b>
              </span>
              <span>
                <small>Observed {selectedAttack.config.norm === "l2" ? "L2" : "L∞"}</small>
                <b>
                  {selectedAttack.config.norm === "l2"
                    ? selectedAttack.metrics.maximum_observed_l2.toFixed(4)
                    : `${(selectedAttack.metrics.maximum_observed_linf * 255).toFixed(2)} / 255`}
                </b>
              </span>
              <span>
                <small>반복 횟수</small>
                <b>{selectedAttack.config.iterations}</b>
              </span>
              <span>
                <small>랜덤 시작</small>
                <b>{selectedAttack.config.random_start ? "Yes" : "No"}</b>
              </span>
            </div>

            {selectedAttack.warnings.map((warning) => (
              <div className="attack-warning" key={warning}>
                <Icon name="activity" size={16} />
                <span>
                  <strong>그래디언트 경고</strong>
                  {warning}
                </span>
              </div>
            ))}

            <button className="button primary full" disabled={busy} type="button" onClick={onOpenAttack}>
              <Icon name="spark" size={16} /> 다른 공격 실행
            </button>
            <small className="inspector-footnote">
              robust 정확도는 clean 정확도와 동일한 샘플 집단을 사용합니다.
            </small>
          </>
        ) : (
          <div className="empty-panel compact-empty">
            <Icon name="spark" size={24} />
            <h3>베이스라인에 도전</h3>
            <p>FGSM·PGD 결과가 여기에 표시됩니다.</p>
            <button className="button primary compact" type="button" onClick={onOpenAttack}>
              첫 공격 실행
            </button>
          </div>
        )}
      </aside>
      {curveRuns.length > 0 && <StrengthCurve runs={curveRuns} />}
      <RobustnessScoreCard
        busy={busy}
        score={score}
        selectedCount={scoreSelection.size}
        onCalculate={onCalculateScore}
      />
    </div>
  );
}
