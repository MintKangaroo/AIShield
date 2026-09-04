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
      <div className="attack-picker" role="group" aria-label="학습 전략">
        {(["adversarial_training", "trades"] as const).map((item) => (
          <button
            className={strategy === item ? "active" : ""}
            key={item}
            type="button"
            onClick={() => setStrategy(item)}
          >
            <span>{item === "trades" ? "TRADES" : "적대적 학습"}</span>
            <small>
              {item === "trades"
                ? "강건성/정확도 트레이드오프 목적함수"
                : "경계 적대 입력으로 직접 학습"}
            </small>
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
          <span>원본 모델</span>
          <select value={modelId} onChange={(event) => setModelId(event.target.value)}>
            {compatibleModels.map((model) => (
              <option key={model.id} value={model.id}>
                {model.name} · seed {model.seed}
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
          <span>에폭</span>
          <input
            max={100}
            min={1}
            type="number"
            value={epochs}
            onChange={(event) => setEpochs(Number(event.target.value))}
          />
        </label>
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
          <span>공격 반복</span>
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
          <span>학습률</span>
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
      <div className="form-row two">
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
        <label className="check-field">
          <input
            checked={queued}
            type="checkbox"
            onChange={(event) => setQueued(event.target.checked)}
          />
          <span>
            백그라운드 작업으로 실행
            <small>요청을 열어두지 않고 작업 페이지에서 진행 상황을 추적합니다.</small>
          </span>
        </label>
      </div>
      <div className="policy-note">
        <Icon name="fingerprint" />
        <p>
          학습은 원본 모델을 변형하지 않고 복제합니다. 학습된 체크포인트는 가중치 전용·콘텐츠 주소 state dict으로 해시된 증거와 함께 저장됩니다.
        </p>
      </div>
      <div className="dialog-actions">
        <button className="button ghost" type="button" onClick={onCancel}>
          취소
        </button>
        <button className="button primary" disabled={!datasetId || !modelId || busy} type="submit">
          <Icon name="layers" size={16} />
          {busy ? "제출 중…" : queued ? "학습 작업 큐잉" : "지금 학습"}
        </button>
      </div>
    </form>
  );
}
