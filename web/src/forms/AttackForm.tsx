import { type FormEvent, useState } from "react";

import { attackAlgorithms, attackProfiles } from "../attacks";
import { Icon } from "../components/Icon";
import { parseSampleCap, useCompatibleModels, useModelSelection } from "../hooks/useCompatibleModels";
import type { AttackAlgorithm, AttackRequest, DatasetRecord, ModelVersionRecord } from "../types";

export function AttackForm({
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
  const [algorithm, setAlgorithm] = useState<AttackAlgorithm>("fgsm");
  const [datasetId, setDatasetId] = useState(datasets[0]?.id ?? "");
  const compatibleModels = useCompatibleModels(datasets, models, datasetId);
  const [modelId, setModelId] = useModelSelection(compatibleModels);
  const [epsilon, setEpsilon] = useState(8);
  const [iterations, setIterations] = useState(10);
  const [batchSize, setBatchSize] = useState(64);
  const [maxSamples, setMaxSamples] = useState("256");

  const profile = attackProfiles[algorithm];

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
      max_samples: parseSampleCap(maxSamples),
    };
    if (profile.iterative) {
      payload.norm = profile.norm;
      payload.step_size = Math.min(2 / 255, epsilonValue);
      payload.iterations = iterations;
      payload.random_start = profile.randomStart;
    }
    void onSubmit(payload);
  }

  return (
    <form className="form-grid" onSubmit={submit}>
      <div className="attack-picker" role="group" aria-label="공격 알고리즘">
        {attackAlgorithms.map((item) => (
          <button
            className={algorithm === item ? "active" : ""}
            key={item}
            type="button"
            onClick={() => setAlgorithm(item)}
          >
            <span>{attackProfiles[item].label}</span>
            <small>{attackProfiles[item].description}</small>
          </button>
        ))}
      </div>
      <div className="form-row two">
        <label>
          <span>데이터셋 split</span>
          <select value={datasetId} onChange={(event) => setDatasetId(event.target.value)}>
            {datasets.map((dataset) => (
              <option key={dataset.id} value={dataset.id}>
                {dataset.name.toUpperCase()} · {dataset.split}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>모델 버전</span>
          <select value={modelId} onChange={(event) => setModelId(event.target.value)}>
            {compatibleModels.map((model) => (
              <option key={model.id} value={model.id}>
                {model.architecture} · {model.device.toUpperCase()}
              </option>
            ))}
          </select>
          {!compatibleModels.length && (
            <small className="field-warning">
              이 데이터셋에 호환되는 모델이 적재되지 않았습니다.
            </small>
          )}
        </label>
      </div>
      <div className="form-row">
        <label>
          <span>엡실론 / 255</span>
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
          <span>반복 횟수</span>
          <input
            disabled={!profile.iterative}
            max={100}
            min={1}
            type="number"
            value={profile.iterative ? iterations : 1}
            onChange={(event) => setIterations(Number(event.target.value))}
          />
        </label>
        <label>
          <span>샘플 상한</span>
          <input
            min={1}
            placeholder="전체 샘플"
            type="number"
            value={maxSamples}
            onChange={(event) => setMaxSamples(event.target.value)}
          />
        </label>
      </div>
      <label>
        <span>배치 크기</span>
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
          Inputs are clamped to [0, 1], every perturbation is checked against the configured{" "}
          {profile.norm === "l2" ? "L2" : "L∞"} bound, and attack success is measured only on
          samples classified correctly before attack.
        </p>
      </div>
      <div className="dialog-actions">
        <button className="button ghost" type="button" onClick={onCancel}>
          취소
        </button>
        <button
          className="button primary"
          disabled={!datasetId || !modelId || busy}
          type="submit"
        >
          <Icon name="spark" size={16} />
          {busy ? "적대적 입력 생성 중…" : `${profile.label} 실행`}
        </button>
      </div>
    </form>
  );
}
