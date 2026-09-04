import type { CSSProperties } from "react";

import { Icon } from "../components/Icon";
import { RunsTable } from "../components/RunsTable";
import { formatDate, formatPercent, shortHash } from "../format";
import type {
  BaselineRunRecord,
  BaselineVerification,
  DatasetRecord,
  ModelVersionRecord,
} from "../types";

export function RunsPage({
  baselines,
  busy,
  datasets,
  models,
  onExport,
  onOpenBaseline,
  onSelectRun,
  onVerify,
  selectedDataset,
  selectedModel,
  selectedRun,
  verification,
}: {
  baselines: BaselineRunRecord[];
  busy: boolean;
  datasets: DatasetRecord[];
  models: ModelVersionRecord[];
  onExport: (baselineId: string) => Promise<void>;
  onOpenBaseline: () => void;
  onSelectRun: (id: string) => void;
  onVerify: (run: BaselineRunRecord) => void;
  selectedDataset: DatasetRecord | undefined;
  selectedModel: ModelVersionRecord | undefined;
  selectedRun: BaselineRunRecord | null;
  verification: BaselineVerification | undefined;
}) {
  return (
    <div className="page-content split-layout">
      <section className="panel runs-panel">
        <div className="panel-heading">
          <div>
            <span className="kicker">전체 증거</span>
            <h3>{baselines.length} completed baselines</h3>
          </div>
          <button className="button secondary compact" type="button" onClick={onOpenBaseline}>
            <Icon name="plus" size={15} /> 새 실행
          </button>
        </div>
        <RunsTable
          datasets={datasets}
          models={models}
          runs={baselines}
          selectedId={selectedRun?.id}
          onSelect={onSelectRun}
        />
      </section>

      <aside className="panel inspector">
        {selectedRun ? (
          <>
            <div className="inspector-top">
              <span className="sealed large">
                <Icon name="check" size={14} /> 증거 봉인됨
              </span>
              <span className="mono faint">{formatDate(selectedRun.created_at)}</span>
            </div>
            <h2>{selectedModel?.architecture ?? "모델 베이스라인"}</h2>
            <p>
              {selectedDataset?.name.toUpperCase()} / {selectedDataset?.split} · seed{" "}
              {selectedRun.config.seed}
            </p>
            <div
              className="score-ring"
              style={{ "--score": selectedRun.metrics.clean_accuracy } as CSSProperties}
            >
              <div>
                <strong>{formatPercent(selectedRun.metrics.clean_accuracy)}</strong>
                <span>clean 정확도</span>
              </div>
            </div>
            <div className="metric-pairs">
              <span>
                <small>평균 손실</small>
                <b>{selectedRun.metrics.mean_loss.toFixed(4)}</b>
              </span>
              <span>
                <small>샘플당 지연</small>
                <b>{selectedRun.metrics.latency.mean_ms_per_sample.toFixed(2)} ms</b>
              </span>
              <span>
                <small>샘플 수</small>
                <b>{selectedRun.metrics.evaluated_samples.toLocaleString()}</b>
              </span>
              <span>
                <small>아티팩트</small>
                <b>{selectedRun.artifacts.length}</b>
              </span>
            </div>
            <div className="hash-stack">
              <span>
                <small>모델 state</small>
                <code>{shortHash(selectedRun.model_state_sha256)}</code>
              </span>
              <span>
                <small>데이터셋 manifest</small>
                <code>{shortHash(selectedRun.dataset_manifest_sha256)}</code>
              </span>
              <span>
                <small>예측</small>
                <code>{shortHash(selectedRun.metrics.prediction_sha256)}</code>
              </span>
            </div>
            {verification && (
              <div className={`verification-result ${verification.reproducible ? "pass" : "fail"}`}>
                <Icon name={verification.reproducible ? "check" : "close"} />
                <span>
                  <strong>
                    {verification.reproducible ? "재현 통과" : "불일치 감지"}
                  </strong>
                  {verification.checks.filter((check) => check.passed).length}/
                  {verification.checks.length} deterministic checks passed
                </span>
              </div>
            )}
            <button
              className="button primary full"
              disabled={busy}
              type="button"
              onClick={() => onVerify(selectedRun)}
            >
              <Icon name="refresh" size={16} />
              {busy ? "동일 실행 재생 중…" : "동일 재실행 검증"}
            </button>
            <button
              className="button secondary full"
              disabled={busy}
              type="button"
              onClick={() => void onExport(selectedRun.id)}
            >
              <Icon name="download" size={16} />
              실험 envelope 내보내기
            </button>
            <small className="inspector-footnote">
              실측 지연은 기록하되 합격/불합격에서는 제외합니다.
            </small>
          </>
        ) : (
          <div className="empty-panel compact-empty">
            <Icon name="activity" size={24} />
            <h3>베이스라인 선택</h3>
            <p>실행 증거가 여기에 표시됩니다.</p>
          </div>
        )}
      </aside>
    </div>
  );
}
