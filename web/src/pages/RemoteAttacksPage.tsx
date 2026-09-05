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
            <h2>배포 모델 대상 블랙박스 공격</h2>
            <p>
              인가된 원격 분류기에 이미지를 질의하고 score만 돌려받습니다 — 가중치도 그래디언트도 없습니다. 호스트는 allowlist에 있어야 하고 각 실행은 명시적으로 인가되어야 합니다.
            </p>
          </div>
        </div>
        <button className="button secondary compact" type="button" onClick={onOpenRemoteAttack}>
          <Icon name="spark" size={15} /> 블랙박스 공격 실행
        </button>
      </section>

      <section className="panel">
        {runs.length ? (
          <div className="attack-table">
            <div className="attack-head remote-head">
              <span>대상</span>
              <span>점검</span>
              <span>clean</span>
              <span>robust</span>
              <span>성공</span>
              <span>질의 수</span>
              <span>경계</span>
            </div>
            {runs.map((run) => {
              const dataset = datasets.find((item) => item.id === run.dataset_id);
              return (
                <div className="attack-row remote-row" key={run.id}>
                  <span className="attack-name">
                    <i>{run.config.algorithm === "boundary" ? "BOUNDARY" : "SQUARE"}</i>
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
            <h3>아직 원격 공격이 없습니다</h3>
            <p>
              Point AIShield at an image classifier you are authorized to test. Set
              <code> AISHIELD_ATTACK_TARGETS_ALLOWLIST</code> on the server first — an empty
              allowlist refuses every target.
            </p>
            <button className="button primary compact" type="button" onClick={onOpenRemoteAttack}>
              대상 설정
            </button>
          </div>
        )}
      </section>

      {runs[0]?.warnings.length ? (
        <div className="attack-warning">
          <Icon name="activity" size={16} />
          <span>
            <strong>해석</strong>
            {runs[0].warnings[0]}
          </span>
        </div>
      ) : null}
    </div>
  );
}
