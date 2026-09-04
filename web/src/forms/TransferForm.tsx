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
        <span>데이터셋 split</span>
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
          <span>대리 모델</span>
          <select value={surrogateId} onChange={(event) => setSurrogateId(event.target.value)}>
            {compatibleModels.map((model) => (
              <option key={model.id} value={model.id}>
                {model.name} · seed {model.seed}
              </option>
            ))}
          </select>
          <small className="field-hint">여기서 섭동이 생성됩니다.</small>
        </label>
        <label>
          <span>대상 모델</span>
          <select value={resolvedTarget} onChange={(event) => setTargetId(event.target.value)}>
            {targetChoices.map((model) => (
              <option key={model.id} value={model.id}>
                {model.name} · seed {model.seed}
              </option>
            ))}
          </select>
          {!targetChoices.length && (
            <small className="field-warning">
              전이를 측정하려면 두 번째 호환 모델을 적재하세요.
            </small>
          )}
        </label>
      </div>
      <div className="form-row">
        <label>
          <span>공격</span>
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
      <div className="policy-note attack-note">
        <Icon name="transfer" />
        <p>
          대상 모델은 그래디언트를 노출하지 않습니다. 이것은 블랙박스 증거입니다: white-box 접근 없이 공격자가 달성할 수 있는 범위를 한정하며, 직접 공격을 대체하지 않습니다.
        </p>
      </div>
      <div className="dialog-actions">
        <button className="button ghost" type="button" onClick={onCancel}>
          취소
        </button>
        <button className="button primary" disabled={!canSubmit || busy} type="submit">
          <Icon name="transfer" size={16} />
          {busy ? "섭동 전이 중…" : "전이 평가 실행"}
        </button>
      </div>
    </form>
  );
}
