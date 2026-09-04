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
          <span className="kicker">투명 집계</span>
          <h3>강건성 점수</h3>
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
                <span>평균 robust 정확도</span>
              </div>
            </div>
            <dl className="score-facts">
              <div>
                <dt>공식</dt>
                <dd className="mono">{score.formula_version}</dd>
              </div>
              <div>
                <dt>증거 커버리지</dt>
                <dd>{formatPercent(score.evidence_coverage)}</dd>
              </div>
              <div>
                <dt>사용된 공격</dt>
                <dd>{score.attacks_used.map((item) => item.toUpperCase()).join(", ")}</dd>
              </div>
              <div>
                <dt>집계된 실행</dt>
                <dd>{score.attack_run_ids.length}</dd>
              </div>
            </dl>
          </div>
          {score.warnings.map((warning) => (
            <div className="attack-warning" key={warning}>
              <Icon name="activity" size={16} />
              <span>
                <strong>해석 한계</strong>
                {warning}
              </span>
            </div>
          ))}
        </>
      ) : (
        <p className="score-hint">
          같은 모델·데이터셋을 공유하는 공격 실행을 선택해 집계하세요. 점수는 공격별 원본 지표를 대체하지 않으며, 불완전한 알고리즘 커버리지는 숨기지 않고 보고합니다.
        </p>
      )}
    </section>
  );
}
