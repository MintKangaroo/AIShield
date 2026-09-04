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
        <span>데이터셋 split</span>
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
        <span>모델 버전</span>
        <select value={modelId} onChange={(event) => setModelId(event.target.value)}>
          {compatibleModels.map((model) => (
            <option key={model.id} value={model.id}>
              {model.name} · {model.device.toUpperCase()}
            </option>
          ))}
        </select>
        {!compatibleModels.length && (
          <small className="field-warning">이 데이터셋에 호환되는 모델이 적재되지 않았습니다.</small>
        )}
      </label>
      <div className="form-row">
        <label>
          <span>시드</span>
          <input
            max={4_294_967_295}
            min={0}
            type="number"
            value={seed}
            onChange={(event) => setSeed(Number(event.target.value))}
          />
        </label>
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
      <div className="policy-note">
        <Icon name="fingerprint" />
        <p>
          결정론적 알고리즘, 모델·데이터셋 해시, 의존성 버전, 순서가 있는 예측 지문이 자동으로 기록됩니다.
        </p>
      </div>
      <div className="dialog-actions">
        <button className="button ghost" type="button" onClick={onCancel}>
          취소
        </button>
        <button className="button primary" disabled={!canSubmit || busy} type="submit">
          <Icon name="play" size={16} />
          {busy ? "평가 실행 중…" : "clean 베이스라인 실행"}
        </button>
      </div>
    </form>
  );
}
