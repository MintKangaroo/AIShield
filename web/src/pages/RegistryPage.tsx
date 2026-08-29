import { Icon } from "../components/Icon";
import { shortHash } from "../format";
import type { DatasetRecord, ModelVersionRecord } from "../types";

export function RegistryPage({
  datasets,
  models,
  onOpenDataset,
  onOpenModel,
}: {
  datasets: DatasetRecord[];
  models: ModelVersionRecord[];
  onOpenDataset: () => void;
  onOpenModel: () => void;
}) {
  return (
    <div className="page-content registry-content">
      <section className="registry-summary">
        <div>
          <span className="summary-icon">
            <Icon name="shield" size={26} />
          </span>
          <div>
            <h2>Trusted runtime inventory</h2>
            <p>
              Process-local handles with immutable identities. Files remain content-addressed in
              configured storage.
            </p>
          </div>
        </div>
        <span className="policy-pill">
          <i /> External downloads{" "}
          {datasets.some((item) => item.source === "approved_public") ? "in use" : "restricted"}
        </span>
      </section>

      <section className="panel registry-section">
        <div className="panel-heading">
          <div>
            <span className="kicker">Input provenance</span>
            <h3>Datasets</h3>
          </div>
          <button className="button secondary compact" type="button" onClick={onOpenDataset}>
            <Icon name="plus" size={15} /> Load dataset
          </button>
        </div>
        <div className="registry-grid">
          {datasets.map((dataset) => (
            <article className="registry-card" key={dataset.id}>
              <div className="registry-card-top">
                <span className="registry-icon dataset">
                  <Icon name="database" />
                </span>
                <span className={`source-badge ${dataset.source}`}>
                  {dataset.source === "generated" ? "Generated" : "Approved public"}
                </span>
              </div>
              <h4>{dataset.name.toUpperCase()}</h4>
              <p>{dataset.version}</p>
              <dl>
                <div>
                  <dt>Split</dt>
                  <dd>{dataset.split}</dd>
                </div>
                <div>
                  <dt>Samples</dt>
                  <dd>{dataset.sample_count.toLocaleString()}</dd>
                </div>
                <div>
                  <dt>Shape</dt>
                  <dd>{dataset.input_shape.join(" × ")}</dd>
                </div>
                <div>
                  <dt>Classes</dt>
                  <dd>{dataset.num_classes}</dd>
                </div>
              </dl>
              <div className="card-hash">
                <Icon name="fingerprint" size={14} />
                <code>{shortHash(dataset.manifest_sha256)}</code>
              </div>
            </article>
          ))}
          {!datasets.length && (
            <button className="add-card" type="button" onClick={onOpenDataset}>
              <span>
                <Icon name="plus" />
              </span>
              <b>Load the first dataset</b>
              <small>Signal-10 works without a download.</small>
            </button>
          )}
        </div>
      </section>

      <section className="panel registry-section">
        <div className="panel-heading">
          <div>
            <span className="kicker">Model integrity</span>
            <h3>Model versions</h3>
          </div>
          <button
            className="button secondary compact"
            disabled={!datasets.length}
            type="button"
            onClick={onOpenModel}
          >
            <Icon name="plus" size={15} /> Create model
          </button>
        </div>
        <div className="registry-grid">
          {models.map((model) => (
            <article className="registry-card" key={model.id}>
              <div className="registry-card-top">
                <span className="registry-icon model">
                  <Icon name="layers" />
                </span>
                <span className="source-badge generated">{model.device.toUpperCase()}</span>
              </div>
              <h4>{model.name}</h4>
              <p>
                {model.architecture} · seed {model.seed}
              </p>
              <dl>
                <div>
                  <dt>Parameters</dt>
                  <dd>{model.parameter_count.toLocaleString()}</dd>
                </div>
                <div>
                  <dt>Classes</dt>
                  <dd>{model.num_classes}</dd>
                </div>
                <div>
                  <dt>Channels</dt>
                  <dd>{model.input_channels}</dd>
                </div>
                <div>
                  <dt>Source</dt>
                  <dd>{model.source === "trained" ? "Trained" : "Initialized"}</dd>
                </div>
              </dl>
              <div className="card-hash">
                <Icon name="fingerprint" size={14} />
                <code>{shortHash(model.state_dict_sha256)}</code>
              </div>
            </article>
          ))}
          {!models.length && (
            <button
              className="add-card"
              disabled={!datasets.length}
              type="button"
              onClick={onOpenModel}
            >
              <span>
                <Icon name="plus" />
              </span>
              <b>Create the first model</b>
              <small>Start with a deterministic SmallCNN.</small>
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
