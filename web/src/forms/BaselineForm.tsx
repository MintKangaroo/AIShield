import { type FormEvent, useState } from "react";

import { Icon } from "../components/Icon";
import { parseSampleCap, useCompatibleModels, useModelSelection } from "../hooks/useCompatibleModels";
import type { BaselineRequest, DatasetRecord, ModelVersionRecord } from "../types";

export function BaselineForm({
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
  const compatibleModels = useCompatibleModels(datasets, models, datasetId);
  const [modelId, setModelId] = useModelSelection(compatibleModels);
  const [seed, setSeed] = useState(1729);
  const [batchSize, setBatchSize] = useState(64);
  const [maxSamples, setMaxSamples] = useState("256");

  function submit(event: FormEvent) {
    event.preventDefault();
    void onSubmit({
      model_version_id: modelId,
      dataset_id: datasetId,
      seed,
      batch_size: batchSize,
      max_samples: parseSampleCap(maxSamples),
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
              {dataset.name.toUpperCase()} · {dataset.split} ·{" "}
              {dataset.sample_count.toLocaleString()} samples
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
