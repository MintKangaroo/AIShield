import { useState } from "react";

import { Icon } from "../components/Icon";
import type { DatasetRecord } from "../types";

export function ModelForm({
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
        <span>호환 데이터셋</span>
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
        <span>초기화 시드</span>
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
          내장 SmallCNN은 결정론적으로 초기화되어 가중치 전용·콘텐츠 주소 PyTorch state dict으로 저장됩니다.
        </p>
      </div>
      <div className="dialog-actions">
        <button className="button ghost" type="button" onClick={onCancel}>
          취소
        </button>
        <button className="button primary" disabled={!datasetId || busy} type="submit">
          <Icon name="layers" size={16} />
          {busy ? "모델 생성 중…" : "SmallCNN 생성"}
        </button>
      </div>
    </form>
  );
}
