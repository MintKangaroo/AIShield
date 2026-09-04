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
            <Icon name="shield" size={14} /> 설계상 재현 가능
          </span>
          <h2>
            증거가 먼저,
            <br />
            <em>확신은 그다음.</em>
          </h2>
          <p>
            강건성을 주장하기 전에 신뢰할 수 있는 clean 베이스라인을 세우세요. AIShield는 모든 결과를 정확한 모델·데이터·시드·런타임·생성 아티팩트에 묶습니다.
          </p>
          <div className="hero-actions">
            <button className="button primary" type="button" onClick={onOpenBaseline}>
              <Icon name="play" size={16} /> 베이스라인 실행
            </button>
            {models.length > 0 && datasets.length > 0 && (
              <button className="button secondary" type="button" onClick={onOpenAttack}>
                <Icon name="spark" size={16} /> 경계 공격 실행
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
                {busy ? "데모 준비 중…" : "제로 다운로드 데모 실행"}
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

      <section className="stat-grid" aria-label="워크스페이스 지표">
        <article>
          <span className="stat-icon lime">
            <Icon name="activity" />
          </span>
          <div>
            <small>최신 clean 정확도</small>
            <strong>
              {selectedRun ? formatPercent(selectedRun.metrics.clean_accuracy) : "—"}
            </strong>
            <span>
              {selectedRun ? `${selectedRun.metrics.evaluated_samples} samples` : "아직 실행 없음"}
            </span>
          </div>
        </article>
        <article>
          <span className="stat-icon violet">
            <Icon name="fingerprint" />
          </span>
          <div>
            <small>재현성</small>
            <strong>{verification ? (verification.reproducible ? "PASS" : "FAIL") : "READY"}</strong>
            <span>
              {verification ? `${verification.checks.length} checks` : "동일 재실행 가능"}
            </span>
          </div>
        </article>
        <article>
          <span className="stat-icon blue">
            <Icon name="shield" />
          </span>
          <div>
            <small>최신 robust 정확도</small>
            <strong>
              {selectedAttack ? formatPercent(selectedAttack.metrics.robust_accuracy) : "—"}
            </strong>
            <span>
              {selectedAttack
                ? `${selectedAttack.config.algorithm.toUpperCase()} · ε ${Math.round(selectedAttack.config.epsilon * 255)}/255`
                : "평가된 공격 없음"}
            </span>
          </div>
        </article>
        <article>
          <span className="stat-icon amber">
            <Icon name="archive" />
          </span>
          <div>
            <small>증거 아티팩트</small>
            <strong>{artifactCount}</strong>
            <span>해시 검증 출력</span>
          </div>
        </article>
      </section>

      <div className="dashboard-grid">
        <section className="panel performance-panel">
          <div className="panel-heading">
            <div>
              <span className="kicker">모델 동작</span>
              <h3>클래스별 recall</h3>
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
              <i className="legend-dot clean" /> 실제 클래스별 recall
            </span>
            <span>
              평균 손실 <b>{selectedRun?.metrics.mean_loss.toFixed(4) ?? "—"}</b>
            </span>
          </div>
        </section>

        <section className="panel matrix-panel">
          <div className="panel-heading">
            <div>
              <span className="kicker">예측 맵</span>
              <h3>혼동 행렬</h3>
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
            <span className="kicker">불변 원장</span>
            <h3>최근 베이스라인 실행</h3>
          </div>
          <button className="text-button" type="button" onClick={onViewAllRuns}>
            모든 실행 보기 <Icon name="arrow" size={15} />
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
