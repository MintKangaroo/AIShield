import { type FormEvent, useState } from "react";

import { Icon } from "../components/Icon";
import { parseSampleCap, useCompatibleModels, useModelSelection } from "../hooks/useCompatibleModels";
import type {
  DatasetRecord,
  ModelVersionRecord,
  TrainingRequest,
  TrainingStrategy,
} from "../types";

export function TrainingForm({
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
  /** `queued` routes the run through the bounded background worker instead of the request. */
  onSubmit: (payload: TrainingRequest, queued: boolean) => Promise<void>;
}) {
  const [datasetId, setDatasetId] = useState(datasets[0]?.id ?? "");
  const compatibleModels = useCompatibleModels(datasets, models, datasetId);
  const [modelId, setModelId] = useModelSelection(compatibleModels);
  const [strategy, setStrategy] = useState<TrainingStrategy>("adversarial_training");
  const [epochs, setEpochs] = useState(1);
  const [epsilon, setEpsilon] = useState(8);
  const [attackIterations, setAttackIterations] = useState(2);
  const [learningRate, setLearningRate] = useState(0.001);
  const [tradesBeta, setTradesBeta] = useState(6);
  const [batchSize, setBatchSize] = useState(64);
  const [maxSamples, setMaxSamples] = useState("256");
  const [queued, setQueued] = useState(true);

  function submit(event: FormEvent) {
    event.preventDefault();
    const epsilonValue = epsilon / 255;
    void onSubmit(
      {
        model_version_id: modelId,
        dataset_id: datasetId,
        strategy,
        seed: 1729,
        epochs,
        batch_size: batchSize,
        max_samples: parseSampleCap(maxSamples),
        epsilon: epsilonValue,
        step_size: Math.min(2 / 255, epsilonValue),
        attack_iterations: attackIterations,
        learning_rate: learningRate,
        trades_beta: tradesBeta,
      },
      queued,
    );
  }

  return (
    <form className="form-grid" onSubmit={submit}>
      <div className="attack-picker" role="group" aria-label="Training strategy">
        {(["adversarial_training", "trades"] as const).map((item) => (
          <button
            className={strategy === item ? "active" : ""}
            key={item}
            type="button"
            onClick={() => setStrategy(item)}
          >
            <span>{item === "trades" ? "TRADES" : "Adversarial"}</span>
            <small>
              {item === "trades"
                ? "Robustness/accuracy trade-off objective"
                : "Train directly on bounded adversarial inputs"}
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
          <span>Source model</span>
          <select value={modelId} onChange={(event) => setModelId(event.target.value)}>
            {compatibleModels.map((model) => (
              <option key={model.id} value={model.id}>
                {model.name} · seed {model.seed}
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
      <div className="form-row">
        <label>
          <span>Epochs</span>
          <input
            max={100}
            min={1}
            type="number"
            value={epochs}
            onChange={(event) => setEpochs(Number(event.target.value))}
          />
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
          <span>Attack iterations</span>
          <input
            max={20}
            min={1}
            type="number"
            value={attackIterations}
            onChange={(event) => setAttackIterations(Number(event.target.value))}
          />
        </label>
      </div>
      <div className="form-row">
        <label>
          <span>Learning rate</span>
          <input
            max={1}
            min={0.00001}
            step={0.0001}
            type="number"
            value={learningRate}
            onChange={(event) => setLearningRate(Number(event.target.value))}
          />
        </label>
        <label>
          <span>TRADES β</span>
          <input
            disabled={strategy !== "trades"}
            max={100}
            min={0}
            step={0.5}
            type="number"
            value={tradesBeta}
            onChange={(event) => setTradesBeta(Number(event.target.value))}
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
        <label className="check-field">
          <input
            checked={queued}
            type="checkbox"
            onChange={(event) => setQueued(event.target.checked)}
          />
          <span>
            Run as a background job
            <small>Track progress on the Jobs page instead of holding the request open.</small>
          </span>
        </label>
      </div>
      <div className="policy-note">
        <Icon name="fingerprint" />
        <p>
          Training copies the source model rather than mutating it. The trained checkpoint is stored
          as a weights-only, content-addressed state dictionary with hashed evidence.
        </p>
      </div>
      <div className="dialog-actions">
        <button className="button ghost" type="button" onClick={onCancel}>
          Cancel
        </button>
        <button className="button primary" disabled={!datasetId || !modelId || busy} type="submit">
          <Icon name="layers" size={16} />
          {busy ? "Submitting…" : queued ? "Queue training job" : "Train now"}
        </button>
      </div>
    </form>
  );
}
