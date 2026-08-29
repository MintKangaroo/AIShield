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
