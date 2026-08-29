import { type FormEvent, useState } from "react";

import { attackProfiles } from "../attacks";
import { Icon } from "../components/Icon";
import { parseSampleCap, useCompatibleModels, useModelSelection } from "../hooks/useCompatibleModels";
import type { AttackAlgorithm, DatasetRecord, DefenseRequest, ModelVersionRecord } from "../types";

/** Preprocessing defenses are only meaningful against gradient-based L-infinity attacks. */
const defenseAttacks: AttackAlgorithm[] = ["fgsm", "bim", "pgd", "autoattack"];

export function DefenseForm({
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
  onSubmit: (payload: DefenseRequest) => Promise<void>;
}) {
  const [datasetId, setDatasetId] = useState(datasets[0]?.id ?? "");
  const compatibleModels = useCompatibleModels(datasets, models, datasetId);
  const [modelId, setModelId] = useModelSelection(compatibleModels);
  const [bitDepth, setBitDepth] = useState(4);
  const [attackAlgorithm, setAttackAlgorithm] = useState<AttackAlgorithm>("pgd");
  const [epsilon, setEpsilon] = useState(8);
  const [iterations, setIterations] = useState(10);
  const [batchSize, setBatchSize] = useState(64);
  const [maxSamples, setMaxSamples] = useState("256");

  const iterative = attackProfiles[attackAlgorithm].iterative;

  function submit(event: FormEvent) {
    event.preventDefault();
    const epsilonValue = epsilon / 255;
    const payload: DefenseRequest = {
      model_version_id: modelId,
      dataset_id: datasetId,
      defense: "bit_depth",
      bit_depth: bitDepth,
      attack_algorithm: attackAlgorithm,
      epsilon: epsilonValue,
      seed: 1729,
      batch_size: batchSize,
      max_samples: parseSampleCap(maxSamples),
    };
    if (iterative) {
      payload.step_size = Math.min(2 / 255, epsilonValue);
      payload.iterations = iterations;
    }
    void onSubmit(payload);
  }

  return (
    <form className="form-grid" onSubmit={submit}>
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
          {!compatibleModels.length && (
            <small className="field-warning">
              No compatible model is loaded for this dataset.
            </small>
          )}
        </label>
      </div>
      <div className="form-row two">
        <label>
          <span>Bit depth</span>
          <input
            max={8}
            min={1}
            type="number"
            value={bitDepth}
            onChange={(event) => setBitDepth(Number(event.target.value))}
          />
          <small className="field-hint">
            Lower depth quantizes harder: {Math.pow(2, bitDepth)} levels per channel.
          </small>
        </label>
        <label>
          <span>Adaptive attack</span>
          <select
            value={attackAlgorithm}
            onChange={(event) => setAttackAlgorithm(event.target.value as AttackAlgorithm)}
          >
            {defenseAttacks.map((item) => (
              <option key={item} value={item}>
                {attackProfiles[item].label}
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
            disabled={!iterative}
            max={100}
            min={1}
            type="number"
            value={iterative ? iterations : 1}
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
          The same sample population is measured before the defense, after the defense, and again
          under a defense-aware adaptive attack. A flat adaptive gradient is reported as masking,
          not as robustness.
        </p>
      </div>
      <div className="dialog-actions">
        <button className="button ghost" type="button" onClick={onCancel}>
          Cancel
        </button>
        <button className="button primary" disabled={!datasetId || !modelId || busy} type="submit">
          <Icon name="shield" size={16} />
          {busy ? "Evaluating defense…" : "Run defense evaluation"}
        </button>
      </div>
    </form>
  );
}
