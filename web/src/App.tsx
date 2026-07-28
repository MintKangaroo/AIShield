import {
  type CSSProperties,
  type FormEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useState,
} from "react";

import { api } from "./api";
import type {
  AttackRequest,
  AttackRunRecord,
  BaselineRequest,
  BaselineRunRecord,
  BaselineVerification,
  DatasetRecord,
  HealthResponse,
  ModelVersionRecord,
} from "./types";

type ApiState = "checking" | "ready" | "offline";
type Page = "overview" | "runs" | "attacks" | "registry" | "artifacts";
type DialogName = "baseline" | "attack" | "dataset" | "model" | null;
type IconName =
  | "activity"
  | "archive"
  | "arrow"
  | "beaker"
  | "check"
  | "chevron"
  | "close"
  | "database"
  | "download"
  | "fingerprint"
  | "grid"
  | "layers"
  | "play"
  | "plus"
  | "refresh"
  | "server"
  | "shield"
  | "spark"
  | "terminal";

interface Toast {
  tone: "success" | "error";
  message: string;
}

const pageCopy: Record<Page, { eyebrow: string; title: string; description: string }> = {
  overview: {
    eyebrow: "Mission control",
    title: "Research overview",
    description: "A live view of model evidence, reproducibility, and evaluation health.",
  },
  runs: {
    eyebrow: "Experiment ledger",
    title: "Baseline runs",
    description: "Inspect immutable metrics and verify an exact-configuration rerun.",
  },
  attacks: {
    eyebrow: "Adversarial laboratory",
    title: "Attack evaluations",
    description: "Compare paired clean and robust accuracy under bounded FGSM and PGD.",
  },
  registry: {
    eyebrow: "Trusted inventory",
    title: "Model & dataset registry",
    description: "Every runtime object is bound to versioned, content-addressed evidence.",
  },
  artifacts: {
    eyebrow: "Evidence vault",
    title: "Generated artifacts",
    description: "Download machine-readable reports and publication-ready matrices.",
  },
};

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    activity: <path d="M3 12h4l2.2-6 4.2 12 2.1-6H21" />,
    archive: (
      <>
        <path d="M4 7h16v13H4zM3 3h18v4H3z" />
        <path d="M9 11h6" />
      </>
    ),
    arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
    beaker: (
      <>
        <path d="M9 3h6m-5 0v6l-5 9a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-9V3" />
        <path d="M7.5 15h9" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    chevron: <path d="m9 18 6-6-6-6" />,
    close: <path d="m6 6 12 12M18 6 6 18" />,
    database: (
      <>
        <ellipse cx="12" cy="5" rx="8" ry="3" />
        <path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7" />
      </>
    ),
    download: <path d="M12 3v12m-5-5 5 5 5-5M5 21h14" />,
    fingerprint: (
      <>
        <path d="M6.5 10a5.5 5.5 0 0 1 11 0c0 5-1.5 8.5-3 11M9 21c1.5-3 2-6.2 2-10a1 1 0 0 1 2 0c0 3.3-.3 6-1.5 9" />
        <path d="M4 17c.7-2.2.8-4.4.8-7a7.2 7.2 0 0 1 14.4 0c0 2.8-.2 5.3-1 7.8" />
      </>
    ),
    grid: (
      <>
        <rect x="3" y="3" width="7" height="7" />
        <rect x="14" y="3" width="7" height="7" />
        <rect x="3" y="14" width="7" height="7" />
        <rect x="14" y="14" width="7" height="7" />
      </>
    ),
    layers: <path d="m12 3 9 5-9 5-9-5 9-5Zm-9 10 9 5 9-5M3 18l9 5 9-5" />,
    play: <path d="m8 5 11 7-11 7V5Z" />,
    plus: <path d="M12 5v14M5 12h14" />,
    refresh: <path d="M20 6v5h-5M4 18v-5h5M6.1 8A7 7 0 0 1 18.5 6.5L20 11M4 13l1.5 4.5A7 7 0 0 0 18 16" />,
    server: (
      <>
        <rect x="3" y="4" width="18" height="6" rx="2" />
        <rect x="3" y="14" width="18" height="6" rx="2" />
        <path d="M7 7h.01M7 17h.01" />
      </>
    ),
    shield: <path d="M12 3 20 6v5c0 5.2-3.3 8.5-8 10-4.7-1.5-8-4.8-8-10V6l8-3Zm-3 9 2 2 4-5" />,
    spark: <path d="m12 3 1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3Zm6 13 .7 2.3L21 19l-2.3.7L18 22l-.7-2.3L15 19l2.3-.7L18 16Z" />,
    terminal: <path d="m4 6 5 5-5 5m7 0h8" />,
  };

  return (
    <svg
      aria-hidden="true"
      className="icon"
      fill="none"
      height={size}
      viewBox="0 0 24 24"
      width={size}
    >
      <g stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7">
        {paths[name]}
      </g>
    </svg>
  );
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function shortHash(value: string) {
  return `${value.slice(0, 7)}…${value.slice(-5)}`;
}

function sortRuns(runs: BaselineRunRecord[]) {
  return [...runs].sort(
    (left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
  );
}

function sortAttacks(attacks: AttackRunRecord[]) {
  return [...attacks].sort(
    (left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
  );
}

function Dialog({
  children,
  description,
  onClose,
  title,
}: {
  children: ReactNode;
  description: string;
  onClose: () => void;
  title: string;
}) {
  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        aria-labelledby="dialog-title"
        aria-modal="true"
        className="dialog"
        role="dialog"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="dialog-header">
          <div>
            <span className="kicker">New evidence</span>
            <h2 id="dialog-title">{title}</h2>
            <p>{description}</p>
          </div>
          <button aria-label="Close dialog" className="icon-button" type="button" onClick={onClose}>
            <Icon name="close" />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}

function BaselineForm({
  busy,
  datasets,
  models,
  onCancel,
  onSubmit,
}: {
  busy: boolean;
  datasets: DatasetRecord[];
  models: ModelVersionRecord[];
  onCancel: () => void;
  onSubmit: (payload: BaselineRequest) => Promise<void>;
}) {
  const [datasetId, setDatasetId] = useState(datasets[0]?.id ?? "");
  const compatibleModels = models.filter((model) => {
    const dataset = datasets.find((item) => item.id === datasetId);
    return (
      dataset &&
      model.input_channels === dataset.input_shape[0] &&
      model.num_classes === dataset.num_classes
    );
  });
  const [modelId, setModelId] = useState(compatibleModels[0]?.id ?? models[0]?.id ?? "");
  const [seed, setSeed] = useState(1729);
  const [batchSize, setBatchSize] = useState(64);
  const [maxSamples, setMaxSamples] = useState("256");

  useEffect(() => {
    if (!compatibleModels.some((model) => model.id === modelId)) {
      setModelId(compatibleModels[0]?.id ?? "");
    }
  }, [compatibleModels, modelId]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const parsedSamples = maxSamples.trim() ? Number(maxSamples) : null;
    void onSubmit({
      model_version_id: modelId,
      dataset_id: datasetId,
      seed,
      batch_size: batchSize,
      max_samples: parsedSamples,
      warmup_batches: 1,
    });
  }

  const canSubmit = Boolean(datasetId && modelId && compatibleModels.length);

  return (
    <form className="form-grid" onSubmit={submit}>
      <label>
        <span>Dataset split</span>
        <select value={datasetId} onChange={(event) => setDatasetId(event.target.value)}>
          {datasets.map((dataset) => (
            <option key={dataset.id} value={dataset.id}>
              {dataset.name.toUpperCase()} · {dataset.split} · {dataset.sample_count.toLocaleString()}{" "}
              samples
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>Model version</span>
        <select value={modelId} onChange={(event) => setModelId(event.target.value)}>
          {compatibleModels.map((model) => (
            <option key={model.id} value={model.id}>
              {model.name} · {model.device.toUpperCase()}
            </option>
          ))}
        </select>
        {!compatibleModels.length && (
          <small className="field-warning">No compatible model is loaded for this dataset.</small>
        )}
      </label>
      <div className="form-row">
        <label>
          <span>Seed</span>
          <input
            max={4_294_967_295}
            min={0}
            type="number"
            value={seed}
            onChange={(event) => setSeed(Number(event.target.value))}
          />
        </label>
        <label>
          <span>Batch size</span>
          <input
            max={4096}
            min={1}
            type="number"
            value={batchSize}
            onChange={(event) => setBatchSize(Number(event.target.value))}
          />
        </label>
        <label>
          <span>Sample cap</span>
          <input
            min={1}
            placeholder="All samples"
            type="number"
            value={maxSamples}
            onChange={(event) => setMaxSamples(event.target.value)}
          />
        </label>
      </div>
      <div className="policy-note">
        <Icon name="fingerprint" />
        <p>
          Deterministic algorithms, model and dataset hashes, dependency versions, and ordered
          prediction fingerprints are captured automatically.
        </p>
      </div>
      <div className="dialog-actions">
        <button className="button ghost" type="button" onClick={onCancel}>
          Cancel
        </button>
        <button className="button primary" disabled={!canSubmit || busy} type="submit">
          <Icon name="play" size={16} />
          {busy ? "Running evaluation…" : "Run clean baseline"}
        </button>
      </div>
    </form>
  );
}

function AttackForm({
  busy,
  datasets,
  models,
  onCancel,
  onSubmit,
}: {
  busy: boolean;
  datasets: DatasetRecord[];
  models: ModelVersionRecord[];
  onCancel: () => void;
  onSubmit: (payload: AttackRequest) => Promise<void>;
}) {
  const [algorithm, setAlgorithm] = useState<AttackRequest["algorithm"]>("fgsm");
  const [datasetId, setDatasetId] = useState(datasets[0]?.id ?? "");
  const compatibleModels = models.filter((model) => {
    const dataset = datasets.find((item) => item.id === datasetId);
    return (
      dataset &&
      model.input_channels === dataset.input_shape[0] &&
      model.num_classes === dataset.num_classes
    );
  });
  const [modelId, setModelId] = useState(compatibleModels[0]?.id ?? models[0]?.id ?? "");
  const [epsilon, setEpsilon] = useState(8);
  const [iterations, setIterations] = useState(10);
  const [batchSize, setBatchSize] = useState(64);
  const [maxSamples, setMaxSamples] = useState("256");

  useEffect(() => {
    if (!compatibleModels.some((model) => model.id === modelId)) {
      setModelId(compatibleModels[0]?.id ?? "");
    }
  }, [compatibleModels, modelId]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const epsilonValue = epsilon / 255;
    const payload: AttackRequest = {
      model_version_id: modelId,
      dataset_id: datasetId,
      algorithm,
      epsilon: epsilonValue,
      seed: 1729,
      batch_size: batchSize,
      max_samples: maxSamples.trim() ? Number(maxSamples) : null,
    };
    if (algorithm === "pgd") {
      payload.step_size = Math.min(2 / 255, epsilonValue);
      payload.iterations = iterations;
      payload.random_start = true;
    }
    void onSubmit(payload);
  }

  return (
    <form className="form-grid" onSubmit={submit}>
      <div className="attack-picker" role="group" aria-label="Attack algorithm">
        {(["fgsm", "pgd"] as const).map((item) => (
          <button
            className={algorithm === item ? "active" : ""}
            key={item}
            type="button"
            onClick={() => setAlgorithm(item)}
          >
            <span>{item.toUpperCase()}</span>
            <small>
              {item === "fgsm" ? "Fast single-step gradient attack" : "Iterative projected attack"}
            </small>
          </button>
        ))}
      </div>
      <div className="form-row two">
        <label>
          <span>Dataset split</span>
          <select value={datasetId} onChange={(event) => setDatasetId(event.target.value)}>
            {datasets.map((dataset) => (
              <option key={dataset.id} value={dataset.id}>
                {dataset.name.toUpperCase()} · {dataset.split}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Model version</span>
          <select value={modelId} onChange={(event) => setModelId(event.target.value)}>
            {compatibleModels.map((model) => (
              <option key={model.id} value={model.id}>
                {model.architecture} · {model.device.toUpperCase()}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="form-row">
        <label>
          <span>Epsilon / 255</span>
          <input
            max={255}
            min={0.01}
            step={0.01}
            type="number"
            value={epsilon}
            onChange={(event) => setEpsilon(Number(event.target.value))}
          />
        </label>
        <label>
          <span>Iterations</span>
          <input
            disabled={algorithm === "fgsm"}
            max={100}
            min={1}
            type="number"
            value={algorithm === "fgsm" ? 1 : iterations}
            onChange={(event) => setIterations(Number(event.target.value))}
          />
        </label>
        <label>
          <span>Sample cap</span>
          <input
            min={1}
            placeholder="All samples"
            type="number"
            value={maxSamples}
            onChange={(event) => setMaxSamples(event.target.value)}
          />
        </label>
      </div>
      <label>
        <span>Batch size</span>
        <input
          max={4096}
          min={1}
          type="number"
          value={batchSize}
          onChange={(event) => setBatchSize(Number(event.target.value))}
        />
      </label>
      <div className="policy-note attack-note">
        <Icon name="shield" />
        <p>
          Inputs are clamped to [0, 1], every perturbation is checked against the configured L∞
          bound, and attack success is measured only on samples classified correctly before attack.
        </p>
      </div>
      <div className="dialog-actions">
        <button className="button ghost" type="button" onClick={onCancel}>
          Cancel
        </button>
        <button
          className="button primary"
          disabled={!datasetId || !modelId || busy}
          type="submit"
        >
          <Icon name="spark" size={16} />
          {busy ? "Generating adversarial inputs…" : `Run ${algorithm.toUpperCase()}`}
        </button>
      </div>
    </form>
  );
}

function DatasetForm({
  busy,
  onCancel,
  onSubmit,
}: {
  busy: boolean;
  onCancel: () => void;
  onSubmit: (payload: {
    name: DatasetRecord["name"];
    split: DatasetRecord["split"];
    download: boolean;
  }) => Promise<void>;
}) {
  const [name, setName] = useState<DatasetRecord["name"]>("synthetic");
  const [split, setSplit] = useState<DatasetRecord["split"]>("test");
  const [download, setDownload] = useState(false);

  return (
    <form
      className="form-grid"
      onSubmit={(event) => {
        event.preventDefault();
        void onSubmit({ name, split, download: name === "synthetic" ? false : download });
      }}
    >
      <label>
        <span>Dataset adapter</span>
        <select
          value={name}
          onChange={(event) => {
            setName(event.target.value as DatasetRecord["name"]);
            setDownload(false);
          }}
        >
          <option value="synthetic">Signal-10 · generated locally</option>
          <option value="mnist">MNIST · approved public source</option>
          <option value="cifar10">CIFAR-10 · approved public source</option>
        </select>
      </label>
      <div className="form-row two">
        <label>
          <span>Split</span>
          <select
            value={split}
            onChange={(event) => setSplit(event.target.value as DatasetRecord["split"])}
          >
            <option value="test">Test</option>
            <option value="train">Train</option>
          </select>
        </label>
        <label className={`check-field ${name === "synthetic" ? "disabled" : ""}`}>
          <input
            checked={download}
            disabled={name === "synthetic"}
            type="checkbox"
            onChange={(event) => setDownload(event.target.checked)}
          />
          <span>
            Download if missing
            <small>Requires AISHIELD_ALLOW_PUBLIC_DOWNLOADS=true</small>
          </span>
        </label>
      </div>
      <div className="policy-note">
        <Icon name="shield" />
        <p>
          Arbitrary URLs are never accepted. Public adapters use fixed canonical sources; Signal-10
          is deterministic synthetic data and is not a security benchmark.
        </p>
      </div>
      <div className="dialog-actions">
        <button className="button ghost" type="button" onClick={onCancel}>
          Cancel
        </button>
        <button className="button primary" disabled={busy} type="submit">
          <Icon name="database" size={16} />
          {busy ? "Loading dataset…" : "Load dataset"}
        </button>
      </div>
    </form>
  );
}

function ModelForm({
  busy,
  datasets,
  onCancel,
  onSubmit,
}: {
  busy: boolean;
  datasets: DatasetRecord[];
  onCancel: () => void;
  onSubmit: (payload: { dataset_id: string; seed: number }) => Promise<void>;
}) {
  const [datasetId, setDatasetId] = useState(datasets[0]?.id ?? "");
  const [seed, setSeed] = useState(1729);

  return (
    <form
      className="form-grid"
      onSubmit={(event) => {
        event.preventDefault();
        void onSubmit({ dataset_id: datasetId, seed });
      }}
    >
      <label>
        <span>Compatible dataset</span>
        <select value={datasetId} onChange={(event) => setDatasetId(event.target.value)}>
          {datasets.map((dataset) => (
            <option key={dataset.id} value={dataset.id}>
              {dataset.name.toUpperCase()} · {dataset.input_shape.join("×")} ·{" "}
              {dataset.num_classes} classes
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>Initialization seed</span>
        <input
          max={4_294_967_295}
          min={0}
          type="number"
          value={seed}
          onChange={(event) => setSeed(Number(event.target.value))}
        />
      </label>
      <div className="policy-note">
        <Icon name="layers" />
        <p>
          The built-in SmallCNN is initialized deterministically and stored as a weights-only,
          content-addressed PyTorch state dictionary.
        </p>
      </div>
      <div className="dialog-actions">
        <button className="button ghost" type="button" onClick={onCancel}>
          Cancel
        </button>
        <button className="button primary" disabled={!datasetId || busy} type="submit">
          <Icon name="layers" size={16} />
          {busy ? "Building model…" : "Create SmallCNN"}
        </button>
      </div>
    </form>
  );
}

function ConfusionMatrix({ run }: { run: BaselineRunRecord | null }) {
  if (!run) {
    return (
      <div className="matrix-empty">
        <Icon name="grid" size={24} />
        <span>Run a baseline to generate the matrix</span>
      </div>
    );
  }

  const matrix = run.metrics.confusion_matrix;
  const maximum = Math.max(...matrix.flat(), 1);
  return (
    <div className="matrix-wrap">
      <div className="matrix-y-label">Actual class</div>
      <div
        aria-label="Confusion matrix"
        className="matrix"
        role="img"
        style={{ gridTemplateColumns: `repeat(${matrix.length}, minmax(0, 1fr))` }}
      >
        {matrix.flatMap((row, rowIndex) =>
          row.map((value, columnIndex) => (
            <span
              className="matrix-cell"
              key={`${rowIndex}-${columnIndex}`}
              title={`Actual ${rowIndex}, predicted ${columnIndex}: ${value}`}
              style={{ "--cell-strength": Math.max(0.08, value / maximum) } as CSSProperties}
            >
              {matrix.length <= 10 ? value : ""}
            </span>
          )),
        )}
      </div>
      <div className="matrix-x-label">Predicted class</div>
    </div>
  );
}

function RunsTable({
  datasets,
  models,
  onSelect,
  runs,
  selectedId,
}: {
  datasets: DatasetRecord[];
  models: ModelVersionRecord[];
  onSelect: (id: string) => void;
  runs: BaselineRunRecord[];
  selectedId?: string;
}) {
  if (!runs.length) {
    return (
      <div className="empty-panel">
        <span className="empty-icon">
          <Icon name="beaker" size={22} />
        </span>
        <h3>No baseline evidence yet</h3>
        <p>Load a dataset and model, then run the first deterministic evaluation.</p>
      </div>
    );
  }

  return (
    <div className="runs-table">
      <div className="runs-head">
        <span>Run</span>
        <span>Target</span>
        <span>Clean acc.</span>
        <span>Latency</span>
        <span>Evidence</span>
        <span />
      </div>
      {runs.map((run, index) => {
        const dataset = datasets.find((item) => item.id === run.dataset_id);
        const model = models.find((item) => item.id === run.model_version_id);
        return (
          <button
            className={`run-row ${selectedId === run.id ? "selected" : ""}`}
            key={run.id}
            type="button"
            onClick={() => onSelect(run.id)}
          >
            <span className="run-id">
              <b>BL-{String(runs.length - index).padStart(3, "0")}</b>
              <small>{formatDate(run.created_at)}</small>
            </span>
            <span className="target-cell">
              <b>{model?.architecture ?? "Unknown model"}</b>
              <small>
                {dataset?.name.toUpperCase() ?? "Unknown dataset"} / {dataset?.split ?? "—"}
              </small>
            </span>
            <strong className="metric-value">{formatPercent(run.metrics.clean_accuracy)}</strong>
            <span className="mono">{run.metrics.latency.mean_ms_per_sample.toFixed(2)} ms</span>
            <span className="sealed">
              <Icon name="check" size={13} /> Sealed
            </span>
            <Icon name="chevron" size={16} />
          </button>
        );
      })}
    </div>
  );
}

function AttackTable({
  attacks,
  datasets,
  models,
  onSelect,
  selectedId,
}: {
  attacks: AttackRunRecord[];
  datasets: DatasetRecord[];
  models: ModelVersionRecord[];
  onSelect: (id: string) => void;
  selectedId?: string;
}) {
  if (!attacks.length) {
    return (
      <div className="empty-panel">
        <span className="empty-icon attack">
          <Icon name="spark" size={22} />
        </span>
        <h3>No adversarial evaluations yet</h3>
        <p>Run FGSM for a fast signal or PGD for a stronger iterative check.</p>
      </div>
    );
  }

  return (
    <div className="attack-table">
      <div className="attack-head">
        <span>Attack</span>
        <span>Target</span>
        <span>Clean</span>
        <span>Robust</span>
        <span>Success</span>
        <span>Bound</span>
        <span />
      </div>
      {attacks.map((attack, index) => {
        const dataset = datasets.find((item) => item.id === attack.dataset_id);
        const model = models.find((item) => item.id === attack.model_version_id);
        return (
          <button
            className={`attack-row ${selectedId === attack.id ? "selected" : ""}`}
            key={attack.id}
            type="button"
            onClick={() => onSelect(attack.id)}
          >
            <span className="attack-name">
              <i>{attack.config.algorithm.toUpperCase()}</i>
              <span>
                <b>AT-{String(attacks.length - index).padStart(3, "0")}</b>
                <small>{formatDate(attack.created_at)}</small>
              </span>
            </span>
            <span className="target-cell">
              <b>{model?.architecture ?? "Unknown model"}</b>
              <small>{dataset?.name.toUpperCase() ?? "Unknown dataset"}</small>
            </span>
            <span className="mono">{formatPercent(attack.metrics.clean_accuracy)}</span>
            <strong className="robust-value">
              {formatPercent(attack.metrics.robust_accuracy)}
            </strong>
            <span className="mono">{formatPercent(attack.metrics.attack_success_rate)}</span>
            <span className="bound-chip">ε {Math.round(attack.config.epsilon * 255)}/255</span>
            <Icon name="chevron" size={16} />
          </button>
        );
      })}
    </div>
  );
}

function App() {
  const [page, setPage] = useState<Page>("overview");
  const [apiState, setApiState] = useState<ApiState>("checking");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [datasets, setDatasets] = useState<DatasetRecord[]>([]);
  const [models, setModels] = useState<ModelVersionRecord[]>([]);
  const [baselines, setBaselines] = useState<BaselineRunRecord[]>([]);
  const [attacks, setAttacks] = useState<AttackRunRecord[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedAttackId, setSelectedAttackId] = useState<string | null>(null);
  const [dialog, setDialog] = useState<DialogName>(null);
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [verifications, setVerifications] = useState<Record<string, BaselineVerification>>({});

  const refresh = useCallback(async (quiet = false) => {
    if (!quiet) setRefreshing(true);
    try {
      const healthPayload = await api.health();
      const [datasetPayload, modelPayload, baselinePayload, attackPayload] = await Promise.all([
        api.datasets(),
        api.models(),
        api.baselines(),
        api.attacks(),
      ]);
      setHealth(healthPayload);
      setDatasets(datasetPayload);
      setModels(modelPayload);
      setBaselines(sortRuns(baselinePayload));
      setAttacks(sortAttacks(attackPayload));
      setApiState("ready");
    } catch {
      setApiState("offline");
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (baselines.length && !baselines.some((run) => run.id === selectedId)) {
      setSelectedId(baselines[0].id);
    }
  }, [baselines, selectedId]);

  useEffect(() => {
    if (attacks.length && !attacks.some((attack) => attack.id === selectedAttackId)) {
      setSelectedAttackId(attacks[0].id);
    }
  }, [attacks, selectedAttackId]);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(null), 4200);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const selectedRun =
    baselines.find((run) => run.id === selectedId) ?? baselines[0] ?? null;
  const selectedDataset = datasets.find((item) => item.id === selectedRun?.dataset_id);
  const selectedModel = models.find((item) => item.id === selectedRun?.model_version_id);
  const selectedAttack =
    attacks.find((attack) => attack.id === selectedAttackId) ?? attacks[0] ?? null;
  const attackDataset = datasets.find((item) => item.id === selectedAttack?.dataset_id);
  const attackModel = models.find((item) => item.id === selectedAttack?.model_version_id);
  const artifactCount = baselines.reduce((total, run) => total + run.artifacts.length, 0);
  const latestVerification = selectedRun ? verifications[selectedRun.id] : undefined;
  const copy = pageCopy[page];

  async function perform(action: () => Promise<void>, successMessage: string) {
    setBusy(true);
    try {
      await action();
      setToast({ tone: "success", message: successMessage });
      setDialog(null);
    } catch (error) {
      setToast({
        tone: "error",
        message: error instanceof Error ? error.message : "The operation could not be completed.",
      });
    } finally {
      setBusy(false);
    }
  }

  async function createBaseline(payload: BaselineRequest) {
    await perform(async () => {
      const run = await api.runBaseline(payload);
      await refresh(true);
      setSelectedId(run.id);
      setPage("runs");
    }, "Baseline sealed with reproducible evidence.");
  }

  async function createAttack(payload: AttackRequest) {
    await perform(async () => {
      const attack = await api.runAttack(payload);
      await refresh(true);
      setSelectedAttackId(attack.id);
      setPage("attacks");
    }, `${payload.algorithm.toUpperCase()} evaluation completed within the configured bound.`);
  }

  async function loadDataset(payload: {
    name: DatasetRecord["name"];
    split: DatasetRecord["split"];
    download: boolean;
  }) {
    await perform(async () => {
      await api.loadDataset(payload);
      await refresh(true);
      setPage("registry");
    }, `${payload.name.toUpperCase()} ${payload.split} split loaded.`);
  }

  async function loadModel(payload: { dataset_id: string; seed: number }) {
    await perform(async () => {
      await api.loadSmallCnn(payload);
      await refresh(true);
      setPage("registry");
    }, "Content-addressed SmallCNN model created.");
  }

  async function startDemo() {
    await perform(async () => {
      let dataset = datasets.find(
        (item) => item.name === "synthetic" && item.split === "test",
      );
      if (!dataset) {
        dataset = await api.loadDataset({ name: "synthetic", split: "test", download: false });
      }
      let model = models.find(
        (item) =>
          item.source === "small_cnn" &&
          item.input_channels === dataset.input_shape[0] &&
          item.num_classes === dataset.num_classes,
      );
      if (!model) {
        model = await api.loadSmallCnn({ dataset_id: dataset.id, seed: 1729 });
      }
      const run = await api.runBaseline({
        model_version_id: model.id,
        dataset_id: dataset.id,
        seed: 1729,
        batch_size: 64,
        max_samples: 256,
        warmup_batches: 1,
      });
      const attack = await api.runAttack({
        model_version_id: model.id,
        dataset_id: dataset.id,
        algorithm: "fgsm",
        epsilon: 8 / 255,
        seed: 1729,
        batch_size: 64,
        max_samples: 256,
      });
      await refresh(true);
      setSelectedId(run.id);
      setSelectedAttackId(attack.id);
    }, "Local demo completed. No network download was used.");
  }

  async function verify(run: BaselineRunRecord) {
    await perform(async () => {
      const result = await api.verifyBaseline(run.id);
      setVerifications((current) => ({ ...current, [run.id]: result }));
      await refresh(true);
      setSelectedId(run.id);
    }, "Exact-configuration rerun matched the reference evidence.");
  }

  function openBaselineDialog() {
    if (!datasets.length) {
      setDialog("dataset");
    } else if (!models.length) {
      setDialog("model");
    } else {
      setDialog("baseline");
    }
  }

  function openAttackDialog() {
    if (!datasets.length) {
      setDialog("dataset");
    } else if (!models.length) {
      setDialog("model");
    } else {
      setDialog("attack");
    }
  }

  const navItems: Array<{ id: Page; label: string; icon: IconName; count?: number }> = [
    { id: "overview", label: "Overview", icon: "grid" },
    { id: "runs", label: "Baseline runs", icon: "activity", count: baselines.length },
    { id: "attacks", label: "Attack lab", icon: "spark", count: attacks.length },
    { id: "registry", label: "Registry", icon: "database", count: datasets.length + models.length },
    { id: "artifacts", label: "Artifacts", icon: "archive", count: artifactCount },
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" type="button" onClick={() => setPage("overview")}>
          <span className="brand-mark">
            <Icon name="shield" size={22} />
          </span>
          <span className="brand-copy">
            <strong>AIShield</strong>
            <small>Research console</small>
          </span>
        </button>

        <div className="workspace-switcher">
          <span className="workspace-avatar">AS</span>
          <span>
            <small>Workspace</small>
            <b>AI Security Lab</b>
          </span>
          <Icon name="chevron" size={14} />
        </div>

        <nav aria-label="Primary navigation">
          <span className="nav-label">Workspace</span>
          {navItems.map((item) => (
            <button
              className={`nav-item ${page === item.id ? "active" : ""}`}
              key={item.id}
              type="button"
              onClick={() => setPage(item.id)}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
              {item.count !== undefined && <b>{item.count}</b>}
            </button>
          ))}
          <span className="nav-label research-label">Research</span>
          <div className="future-nav">
            <span>
              <Icon name="shield" /> Defense evaluation
            </span>
            <small>Next milestone</small>
          </div>
        </nav>

        <div className="sidebar-footer">
          <div className="integrity-card">
            <span className="integrity-icon">
              <Icon name="fingerprint" />
            </span>
            <div>
              <strong>Evidence-first</strong>
              <p>Hashes, seeds, environment and raw metrics stay attached.</p>
            </div>
          </div>
          <a href="/api/docs" target="_blank" rel="noreferrer">
            <Icon name="terminal" size={15} />
            API documentation
            <Icon name="arrow" size={14} />
          </a>
        </div>
      </aside>

      <main>
        <header className="topbar">
          <div>
            <span className="kicker">{copy.eyebrow}</span>
            <h1>{copy.title}</h1>
            <p>{copy.description}</p>
          </div>
          <div className="top-actions">
            <span className={`api-status ${apiState}`}>
              <i />
              {apiState === "ready"
                ? `API ${health?.version} · ${health?.compute_device.toUpperCase()}`
                : apiState === "checking"
                  ? "Connecting"
                  : "API offline"}
            </span>
            <button
              aria-label="Refresh workspace"
              className={`icon-button ${refreshing ? "spinning" : ""}`}
              type="button"
              onClick={() => void refresh()}
            >
              <Icon name="refresh" />
            </button>
            <button
              className="button primary compact"
              type="button"
              onClick={page === "attacks" ? openAttackDialog : openBaselineDialog}
            >
              <Icon name="plus" size={16} />
              {page === "attacks" ? "New attack" : "New baseline"}
            </button>
          </div>
        </header>

        {apiState === "offline" && (
          <div className="offline-banner">
            <Icon name="server" />
            <span>
              <strong>The API is offline.</strong> Start <code>aishield-api</code> or the Docker
              stack, then refresh this workspace.
            </span>
            <button type="button" onClick={() => void refresh()}>
              Retry connection
            </button>
          </div>
        )}

        {page === "overview" && (
          <div className="page-content">
            <section className="hero">
              <div className="hero-copy">
                <span className="hero-badge">
                  <Icon name="shield" size={14} /> Reproducible by design
                </span>
                <h2>
                  Evidence before
                  <br />
                  <em>confidence.</em>
                </h2>
                <p>
                  Establish a trusted clean baseline before you claim robustness. AIShield binds
                  every result to the exact model, data, seed, runtime and generated artifacts.
                </p>
                <div className="hero-actions">
                  <button className="button primary" type="button" onClick={openBaselineDialog}>
                    <Icon name="play" size={16} /> Run baseline
                  </button>
                  {models.length > 0 && datasets.length > 0 && (
                    <button className="button secondary" type="button" onClick={openAttackDialog}>
                      <Icon name="spark" size={16} /> Run bounded attack
                    </button>
                  )}
                  {!baselines.length && (
                    <button
                      className="button secondary"
                      disabled={busy || apiState !== "ready"}
                      type="button"
                      onClick={() => void startDemo()}
                    >
                      <Icon name="spark" size={16} />
                      {busy ? "Preparing demo…" : "Launch zero-download demo"}
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

            <section className="stat-grid" aria-label="Workspace metrics">
              <article>
                <span className="stat-icon lime">
                  <Icon name="activity" />
                </span>
                <div>
                  <small>Latest clean accuracy</small>
                  <strong>{selectedRun ? formatPercent(selectedRun.metrics.clean_accuracy) : "—"}</strong>
                  <span>{selectedRun ? `${selectedRun.metrics.evaluated_samples} samples` : "No run yet"}</span>
                </div>
              </article>
              <article>
                <span className="stat-icon violet">
                  <Icon name="fingerprint" />
                </span>
                <div>
                  <small>Reproducibility</small>
                  <strong>{latestVerification ? (latestVerification.reproducible ? "PASS" : "FAIL") : "READY"}</strong>
                  <span>{latestVerification ? `${latestVerification.checks.length} checks` : "Exact rerun available"}</span>
                </div>
              </article>
              <article>
                <span className="stat-icon blue">
                  <Icon name="shield" />
                </span>
                <div>
                  <small>Latest robust accuracy</small>
                  <strong>
                    {selectedAttack ? formatPercent(selectedAttack.metrics.robust_accuracy) : "—"}
                  </strong>
                  <span>
                    {selectedAttack
                      ? `${selectedAttack.config.algorithm.toUpperCase()} · ε ${Math.round(selectedAttack.config.epsilon * 255)}/255`
                      : "No attack evaluated"}
                  </span>
                </div>
              </article>
              <article>
                <span className="stat-icon amber">
                  <Icon name="archive" />
                </span>
                <div>
                  <small>Evidence artifacts</small>
                  <strong>{artifactCount}</strong>
                  <span>Hash-verified outputs</span>
                </div>
              </article>
            </section>

            <div className="dashboard-grid">
              <section className="panel performance-panel">
                <div className="panel-heading">
                  <div>
                    <span className="kicker">Model behavior</span>
                    <h3>Class-level recall</h3>
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
                    <i className="legend-dot clean" /> Recall by true class
                  </span>
                  <span>
                    Mean loss <b>{selectedRun?.metrics.mean_loss.toFixed(4) ?? "—"}</b>
                  </span>
                </div>
              </section>

              <section className="panel matrix-panel">
                <div className="panel-heading">
                  <div>
                    <span className="kicker">Prediction map</span>
                    <h3>Confusion matrix</h3>
                  </div>
                  {selectedRun && <span className="mono faint">{shortHash(selectedRun.metrics.prediction_sha256)}</span>}
                </div>
                <ConfusionMatrix run={selectedRun} />
              </section>
            </div>

            <section className="panel recent-panel">
              <div className="panel-heading">
                <div>
                  <span className="kicker">Immutable ledger</span>
                  <h3>Recent baseline runs</h3>
                </div>
                <button className="text-button" type="button" onClick={() => setPage("runs")}>
                  View all runs <Icon name="arrow" size={15} />
                </button>
              </div>
              <RunsTable
                datasets={datasets}
                models={models}
                runs={baselines.slice(0, 4)}
                selectedId={selectedRun?.id}
                onSelect={(id) => {
                  setSelectedId(id);
                  setPage("runs");
                }}
              />
            </section>
          </div>
        )}

        {page === "runs" && (
          <div className="page-content split-layout">
            <section className="panel runs-panel">
              <div className="panel-heading">
                <div>
                  <span className="kicker">All evidence</span>
                  <h3>{baselines.length} completed baselines</h3>
                </div>
                <button className="button secondary compact" type="button" onClick={openBaselineDialog}>
                  <Icon name="plus" size={15} /> New run
                </button>
              </div>
              <RunsTable
                datasets={datasets}
                models={models}
                runs={baselines}
                selectedId={selectedRun?.id}
                onSelect={setSelectedId}
              />
            </section>

            <aside className="panel inspector">
              {selectedRun ? (
                <>
                  <div className="inspector-top">
                    <span className="sealed large">
                      <Icon name="check" size={14} /> Evidence sealed
                    </span>
                    <span className="mono faint">{formatDate(selectedRun.created_at)}</span>
                  </div>
                  <h2>{selectedModel?.architecture ?? "Model baseline"}</h2>
                  <p>
                    {selectedDataset?.name.toUpperCase()} / {selectedDataset?.split} · seed{" "}
                    {selectedRun.config.seed}
                  </p>
                  <div className="score-ring" style={{ "--score": selectedRun.metrics.clean_accuracy } as CSSProperties}>
                    <div>
                      <strong>{formatPercent(selectedRun.metrics.clean_accuracy)}</strong>
                      <span>clean accuracy</span>
                    </div>
                  </div>
                  <div className="metric-pairs">
                    <span>
                      <small>Mean loss</small>
                      <b>{selectedRun.metrics.mean_loss.toFixed(4)}</b>
                    </span>
                    <span>
                      <small>Latency / sample</small>
                      <b>{selectedRun.metrics.latency.mean_ms_per_sample.toFixed(2)} ms</b>
                    </span>
                    <span>
                      <small>Samples</small>
                      <b>{selectedRun.metrics.evaluated_samples.toLocaleString()}</b>
                    </span>
                    <span>
                      <small>Artifacts</small>
                      <b>{selectedRun.artifacts.length}</b>
                    </span>
                  </div>
                  <div className="hash-stack">
                    <span>
                      <small>Model state</small>
                      <code>{shortHash(selectedRun.model_state_sha256)}</code>
                    </span>
                    <span>
                      <small>Dataset manifest</small>
                      <code>{shortHash(selectedRun.dataset_manifest_sha256)}</code>
                    </span>
                    <span>
                      <small>Predictions</small>
                      <code>{shortHash(selectedRun.metrics.prediction_sha256)}</code>
                    </span>
                  </div>
                  {latestVerification && (
                    <div className={`verification-result ${latestVerification.reproducible ? "pass" : "fail"}`}>
                      <Icon name={latestVerification.reproducible ? "check" : "close"} />
                      <span>
                        <strong>
                          {latestVerification.reproducible ? "Reproduction passed" : "Mismatch detected"}
                        </strong>
                        {latestVerification.checks.filter((check) => check.passed).length}/
                        {latestVerification.checks.length} deterministic checks passed
                      </span>
                    </div>
                  )}
                  <button
                    className="button primary full"
                    disabled={busy}
                    type="button"
                    onClick={() => void verify(selectedRun)}
                  >
                    <Icon name="refresh" size={16} />
                    {busy ? "Replaying exact run…" : "Verify exact rerun"}
                  </button>
                  <small className="inspector-footnote">
                    Wall-clock latency is recorded but excluded from pass/fail.
                  </small>
                </>
              ) : (
                <div className="empty-panel compact-empty">
                  <Icon name="activity" size={24} />
                  <h3>Select a baseline</h3>
                  <p>Run evidence will appear here.</p>
                </div>
              )}
            </aside>
          </div>
        )}

        {page === "attacks" && (
          <div className="page-content split-layout attack-layout">
            <section className="panel runs-panel">
              <div className="panel-heading">
                <div>
                  <span className="kicker">Paired evaluation</span>
                  <h3>{attacks.length} bounded attack runs</h3>
                </div>
                <button className="button secondary compact" type="button" onClick={openAttackDialog}>
                  <Icon name="spark" size={15} /> Run attack
                </button>
              </div>
              <AttackTable
                attacks={attacks}
                datasets={datasets}
                models={models}
                selectedId={selectedAttack?.id}
                onSelect={setSelectedAttackId}
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
                    {selectedAttack.config.algorithm.toUpperCase()} · L∞
                  </span>
                  <h2>{attackModel?.architecture ?? "Adversarial evaluation"}</h2>
                  <p>
                    {attackDataset?.name.toUpperCase()} / {attackDataset?.split} ·{" "}
                    {selectedAttack.metrics.evaluated_samples} samples
                  </p>

                  <div className="accuracy-compare">
                    <div>
                      <span>
                        <small>Clean accuracy</small>
                        <b>{formatPercent(selectedAttack.metrics.clean_accuracy)}</b>
                      </span>
                      <i>
                        <em
                          style={{
                            width: `${selectedAttack.metrics.clean_accuracy * 100}%`,
                          }}
                        />
                      </i>
                    </div>
                    <div className="robust">
                      <span>
                        <small>Robust accuracy</small>
                        <b>{formatPercent(selectedAttack.metrics.robust_accuracy)}</b>
                      </span>
                      <i>
                        <em
                          style={{
                            width: `${selectedAttack.metrics.robust_accuracy * 100}%`,
                          }}
                        />
                      </i>
                    </div>
                  </div>

                  <div className="attack-success">
                    <span>
                      <Icon name="activity" />
                      <small>Attack success rate</small>
                    </span>
                    <strong>{formatPercent(selectedAttack.metrics.attack_success_rate)}</strong>
                    <p>
                      {selectedAttack.metrics.successful_attacks} of{" "}
                      {selectedAttack.metrics.clean_correct_samples} clean-correct samples changed
                      to an incorrect prediction.
                    </p>
                  </div>

                  <div className="metric-pairs attack-config">
                    <span>
                      <small>Epsilon</small>
                      <b>{(selectedAttack.config.epsilon * 255).toFixed(1)} / 255</b>
                    </span>
                    <span>
                      <small>Observed L∞</small>
                      <b>{(selectedAttack.metrics.maximum_observed_linf * 255).toFixed(2)} / 255</b>
                    </span>
                    <span>
                      <small>Iterations</small>
                      <b>{selectedAttack.config.iterations}</b>
                    </span>
                    <span>
                      <small>Random start</small>
                      <b>{selectedAttack.config.random_start ? "Yes" : "No"}</b>
                    </span>
                  </div>

                  {selectedAttack.warnings.map((warning) => (
                    <div className="attack-warning" key={warning}>
                      <Icon name="activity" size={16} />
                      <span>
                        <strong>Gradient warning</strong>
                        {warning}
                      </span>
                    </div>
                  ))}

                  <button
                    className="button primary full"
                    disabled={busy}
                    type="button"
                    onClick={openAttackDialog}
                  >
                    <Icon name="spark" size={16} /> Run another attack
                  </button>
                  <small className="inspector-footnote">
                    Robust accuracy uses the same sample population as clean accuracy.
                  </small>
                </>
              ) : (
                <div className="empty-panel compact-empty">
                  <Icon name="spark" size={24} />
                  <h3>Challenge the baseline</h3>
                  <p>FGSM and PGD results will appear here.</p>
                  <button className="button primary compact" type="button" onClick={openAttackDialog}>
                    Run first attack
                  </button>
                </div>
              )}
            </aside>
          </div>
        )}

        {page === "registry" && (
          <div className="page-content registry-content">
            <section className="registry-summary">
              <div>
                <span className="summary-icon">
                  <Icon name="shield" size={26} />
                </span>
                <div>
                  <h2>Trusted runtime inventory</h2>
                  <p>
                    Process-local handles with immutable identities. Files remain content-addressed
                    in configured storage.
                  </p>
                </div>
              </div>
              <span className="policy-pill"><i /> External downloads {datasets.some((item) => item.source === "approved_public") ? "in use" : "restricted"}</span>
            </section>

            <section className="panel registry-section">
              <div className="panel-heading">
                <div>
                  <span className="kicker">Input provenance</span>
                  <h3>Datasets</h3>
                </div>
                <button className="button secondary compact" type="button" onClick={() => setDialog("dataset")}>
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
                      <div><dt>Split</dt><dd>{dataset.split}</dd></div>
                      <div><dt>Samples</dt><dd>{dataset.sample_count.toLocaleString()}</dd></div>
                      <div><dt>Shape</dt><dd>{dataset.input_shape.join(" × ")}</dd></div>
                      <div><dt>Classes</dt><dd>{dataset.num_classes}</dd></div>
                    </dl>
                    <div className="card-hash">
                      <Icon name="fingerprint" size={14} />
                      <code>{shortHash(dataset.manifest_sha256)}</code>
                    </div>
                  </article>
                ))}
                {!datasets.length && (
                  <button className="add-card" type="button" onClick={() => setDialog("dataset")}>
                    <span><Icon name="plus" /></span>
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
                  onClick={() => setDialog("model")}
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
                    <p>{model.architecture} · seed {model.seed}</p>
                    <dl>
                      <div><dt>Parameters</dt><dd>{model.parameter_count.toLocaleString()}</dd></div>
                      <div><dt>Classes</dt><dd>{model.num_classes}</dd></div>
                      <div><dt>Channels</dt><dd>{model.input_channels}</dd></div>
                      <div><dt>Framework</dt><dd>PyTorch</dd></div>
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
                    onClick={() => setDialog("model")}
                  >
                    <span><Icon name="plus" /></span>
                    <b>Create the first model</b>
                    <small>Start with a deterministic SmallCNN.</small>
                  </button>
                )}
              </div>
            </section>
          </div>
        )}

        {page === "artifacts" && (
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
                <span><b>{baselines.length}</b> runs</span>
                <span><b>2</b> formats</span>
                <span><b>SHA-256</b> integrity</span>
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
                      <i><Icon name={artifact.media_type === "image/png" ? "grid" : "archive"} size={16} /></i>
                      <b>{artifact.kind === "confusion_matrix" ? "Confusion matrix" : "Baseline report"}</b>
                    </span>
                    <span className="mono">BL-{String(baselines.length - runIndex).padStart(3, "0")}</span>
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
                  <span className="empty-icon"><Icon name="archive" /></span>
                  <h3>The evidence vault is empty</h3>
                  <p>Reports and confusion matrices are generated after each baseline.</p>
                </div>
              )}
            </section>
          </div>
        )}
      </main>

      {dialog === "baseline" && (
        <Dialog
          title="Run a clean baseline"
          description="Measure unperturbed model behavior and seal the complete evidence record."
          onClose={() => setDialog(null)}
        >
          <BaselineForm
            busy={busy}
            datasets={datasets}
            models={models}
            onCancel={() => setDialog(null)}
            onSubmit={createBaseline}
          />
        </Dialog>
      )}
      {dialog === "attack" && (
        <Dialog
          title="Run a bounded attack"
          description="Generate adversarial inputs and compare paired clean and robust metrics."
          onClose={() => setDialog(null)}
        >
          <AttackForm
            busy={busy}
            datasets={datasets}
            models={models}
            onCancel={() => setDialog(null)}
            onSubmit={createAttack}
          />
        </Dialog>
      )}
      {dialog === "dataset" && (
        <Dialog
          title="Load a dataset split"
          description="Use generated data locally or an explicitly approved public adapter."
          onClose={() => setDialog(null)}
        >
          <DatasetForm
            busy={busy}
            onCancel={() => setDialog(null)}
            onSubmit={loadDataset}
          />
        </Dialog>
      )}
      {dialog === "model" && (
        <Dialog
          title="Create a model version"
          description="Initialize a dataset-compatible model and bind it to content hashes."
          onClose={() => setDialog(null)}
        >
          <ModelForm
            busy={busy}
            datasets={datasets}
            onCancel={() => setDialog(null)}
            onSubmit={loadModel}
          />
        </Dialog>
      )}

      {toast && (
        <div className={`toast ${toast.tone}`} role="status">
          <span><Icon name={toast.tone === "success" ? "check" : "close"} size={15} /></span>
          {toast.message}
          <button aria-label="Dismiss notification" type="button" onClick={() => setToast(null)}>
            <Icon name="close" size={14} />
          </button>
        </div>
      )}
    </div>
  );
}

export default App;
