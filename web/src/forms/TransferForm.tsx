import { type FormEvent, useState } from "react";

import { attackProfiles } from "../attacks";
import { Icon } from "../components/Icon";
import { parseSampleCap, useCompatibleModels, useModelSelection } from "../hooks/useCompatibleModels";
import type {
  AttackAlgorithm,
  DatasetRecord,
  ModelVersionRecord,
  TransferRequest,
} from "../types";

/** Transfer evidence only makes sense for L-infinity gradient attacks on the surrogate. */
const transferAttacks: AttackAlgorithm[] = ["fgsm", "bim", "pgd", "autoattack"];

export function TransferForm({
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
  onSubmit: (payload: TransferRequest) => Promise<void>;
}) {
  const [datasetId, setDatasetId] = useState(datasets[0]?.id ?? "");
  const compatibleModels = useCompatibleModels(datasets, models, datasetId);
  const [surrogateId, setSurrogateId] = useModelSelection(compatibleModels);
  const [targetId, setTargetId] = useState("");
  const [algorithm, setAlgorithm] = useState<AttackAlgorithm>("pgd");
  const [epsilon, setEpsilon] = useState(8);
  const [iterations, setIterations] = useState(10);
  const [batchSize, setBatchSize] = useState(64);
  const [maxSamples, setMaxSamples] = useState("256");

  const targetChoices = compatibleModels.filter((model) => model.id !== surrogateId);
  const resolvedTarget = targetChoices.some((model) => model.id === targetId)
    ? targetId
    : (targetChoices[0]?.id ?? "");

  function submit(event: FormEvent) {
    event.preventDefault();
    const epsilonValue = epsilon / 255;
    const payload: TransferRequest = {
      surrogate_model_version_id: surrogateId,
      target_model_version_id: resolvedTarget,
      dataset_id: datasetId,
      algorithm,
      epsilon: epsilonValue,
      iterations: attackProfiles[algorithm].iterative ? iterations : 1,
      seed: 1729,
      batch_size: batchSize,
      max_samples: parseSampleCap(maxSamples),
    };
    if (attackProfiles[algorithm].iterative) {
      payload.step_size = Math.min(2 / 255, epsilonValue);
    }
    void onSubmit(payload);
  }

  const canSubmit = Boolean(datasetId && surrogateId && resolvedTarget);

  return (
    <form className="form-grid" onSubmit={submit}>
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
      <div className="form-row two">
        <label>
          <span>Surrogate model</span>
          <select value={surrogateId} onChange={(event) => setSurrogateId(event.target.value)}>
            {compatibleModels.map((model) => (
              <option key={model.id} value={model.id}>
                {model.name} · seed {model.seed}
              </option>
            ))}
          </select>
          <small className="field-hint">Perturbations are generated here.</small>
        </label>
        <label>
          <span>Target model</span>
          <select value={resolvedTarget} onChange={(event) => setTargetId(event.target.value)}>
            {targetChoices.map((model) => (
              <option key={model.id} value={model.id}>
                {model.name} · seed {model.seed}
              </option>
            ))}
          </select>
          {!targetChoices.length && (
            <small className="field-warning">
              Load a second compatible model to measure transfer.
            </small>
          )}
        </label>
      </div>
      <div className="form-row">
        <label>
          <span>Attack</span>
          <select
            value={algorithm}
            onChange={(event) => setAlgorithm(event.target.value as AttackAlgorithm)}
          >
            {transferAttacks.map((item) => (
              <option key={item} value={item}>
                {attackProfiles[item].label}
              </option>
            ))}
          </select>
        </label>
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
            disabled={!attackProfiles[algorithm].iterative}
            max={100}
            min={1}
            type="number"
            value={attackProfiles[algorithm].iterative ? iterations : 1}
            onChange={(event) => setIterations(Number(event.target.value))}
          />
        </label>
      </div>
      <div className="form-row two">
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
      <div className="policy-note attack-note">
        <Icon name="transfer" />
        <p>
          The target model never exposes a gradient. This is black-box evidence: it bounds what an
          attacker achieves without white-box access, and it does not replace a direct attack.
        </p>
      </div>
      <div className="dialog-actions">
        <button className="button ghost" type="button" onClick={onCancel}>
          Cancel
        </button>
        <button className="button primary" disabled={!canSubmit || busy} type="submit">
          <Icon name="transfer" size={16} />
          {busy ? "Transferring perturbations…" : "Run transfer evaluation"}
        </button>
      </div>
    </form>
  );
}
