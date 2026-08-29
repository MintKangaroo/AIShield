import { api } from "../api";
import { Icon } from "../components/Icon";
import { formatBytes, shortHash } from "../format";
import type { BaselineRunRecord } from "../types";

export function ArtifactsPage({
  artifactCount,
  baselines,
}: {
  artifactCount: number;
  baselines: BaselineRunRecord[];
}) {
  return (
    <div className="page-content">
      <section className="evidence-hero">
        <div>
          <span className="summary-icon purple">
            <Icon name="archive" size={26} />
          </span>
          <div>
            <span className="kicker">Portable results</span>
            <h2>{artifactCount} evidence artifacts</h2>
            <p>Every download carries a SHA-256 digest and belongs to one immutable run.</p>
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
          <span>Artifact</span>
          <span>Run</span>
          <span>Media type</span>
          <span>Size</span>
          <span>Digest</span>
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
                  {artifact.kind === "confusion_matrix" ? "Confusion matrix" : "Baseline report"}
                </b>
              </span>
              <span className="mono">
                BL-{String(baselines.length - runIndex).padStart(3, "0")}
              </span>
              <span>{artifact.media_type}</span>
              <span>{formatBytes(artifact.size_bytes)}</span>
              <code>{shortHash(artifact.sha256)}</code>
              <a
                aria-label={`Download ${artifact.kind}`}
                className="download-button"
                href={api.artifactUrl(run.id, artifact.id)}
              >
                <Icon name="download" size={16} />
              </a>
            </div>
          )),
        )}
        {!artifactCount && (
          <div className="empty-panel">
            <span className="empty-icon">
              <Icon name="archive" />
            </span>
            <h3>The evidence vault is empty</h3>
            <p>Reports and confusion matrices are generated after each baseline.</p>
          </div>
        )}
      </section>
    </div>
  );
}
