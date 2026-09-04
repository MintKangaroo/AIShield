import { Icon } from "../components/Icon";
import { formatBytes, shortHash } from "../format";
import type { BaselineRunRecord } from "../types";

export function ArtifactsPage({
  artifactCount,
  baselines,
  onDownload,
}: {
  artifactCount: number;
  baselines: BaselineRunRecord[];
  onDownload: (baselineId: string, artifactId: string, filename: string) => Promise<void>;
}) {
  return (
    <div className="page-content">
      <section className="evidence-hero">
        <div>
          <span className="summary-icon purple">
            <Icon name="archive" size={26} />
          </span>
          <div>
            <span className="kicker">이식 가능한 결과</span>
            <h2>{artifactCount} evidence artifacts</h2>
            <p>모든 다운로드는 SHA-256 다이제스트를 가지며 하나의 불변 실행에 속합니다.</p>
          </div>
        </div>
        <div className="evidence-stats">
          <span>
            <b>{baselines.length}</b> runs
          </span>
          <span>
            <b>2</b> formats
          </span>
          <span>
            <b>SHA-256</b> integrity
          </span>
        </div>
      </section>
      <section className="panel artifact-list">
        <div className="artifact-head">
          <span>아티팩트</span>
          <span>실행</span>
          <span>미디어 타입</span>
          <span>크기</span>
          <span>다이제스트</span>
          <span />
        </div>
        {baselines.flatMap((run, runIndex) =>
          run.artifacts.map((artifact) => (
            <div className="artifact-row" key={artifact.id}>
              <span className="artifact-name">
                <i>
                  <Icon name={artifact.media_type === "image/png" ? "grid" : "archive"} size={16} />
                </i>
                <b>
                  {artifact.kind === "confusion_matrix" ? "혼동 행렬" : "베이스라인 리포트"}
                </b>
              </span>
              <span className="mono">
                BL-{String(baselines.length - runIndex).padStart(3, "0")}
              </span>
              <span>{artifact.media_type}</span>
              <span>{formatBytes(artifact.size_bytes)}</span>
              <code>{shortHash(artifact.sha256)}</code>
              <button
                aria-label={`Download ${artifact.kind}`}
                className="download-button"
                type="button"
                onClick={() =>
                  void onDownload(
                    run.id,
                    artifact.id,
                    `${artifact.kind}-${artifact.id}${
                      artifact.media_type === "image/png" ? ".png" : ".json"
                    }`,
                  )
                }
              >
                <Icon name="download" size={16} />
              </button>
            </div>
          )),
        )}
        {!artifactCount && (
          <div className="empty-panel">
            <span className="empty-icon">
              <Icon name="archive" />
            </span>
            <h3>증거 보관소가 비어 있습니다</h3>
            <p>리포트와 혼동 행렬은 각 베이스라인 후 생성됩니다.</p>
          </div>
        )}
      </section>
    </div>
  );
}
