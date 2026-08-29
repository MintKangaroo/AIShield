import { useState } from "react";

import { Icon } from "../components/Icon";
import type { DatasetRecord } from "../types";

export function DatasetForm({
  busy,
  onCancel,
  onSubmit,
}: {
  busy: boolean;
  onCancel: () => void;
  onSubmit: (payload: {
    name: DatasetRecord["name"];
    split: DatasetRecord["split"];
    download: boolean;
  }) => Promise<void>;
}) {
  const [name, setName] = useState<DatasetRecord["name"]>("synthetic");
  const [split, setSplit] = useState<DatasetRecord["split"]>("test");
  const [download, setDownload] = useState(false);

  return (
    <form
      className="form-grid"
      onSubmit={(event) => {
        event.preventDefault();
        void onSubmit({ name, split, download: name === "synthetic" ? false : download });
      }}
    >
      <label>
        <span>Dataset adapter</span>
        <select
          value={name}
          onChange={(event) => {
            setName(event.target.value as DatasetRecord["name"]);
            setDownload(false);
          }}
        >
          <option value="synthetic">Signal-10 · generated locally</option>
          <option value="mnist">MNIST · approved public source</option>
          <option value="cifar10">CIFAR-10 · approved public source</option>
        </select>
      </label>
      <div className="form-row two">
        <label>
          <span>Split</span>
          <select
            value={split}
            onChange={(event) => setSplit(event.target.value as DatasetRecord["split"])}
          >
            <option value="test">Test</option>
            <option value="train">Train</option>
          </select>
        </label>
        <label className={`check-field ${name === "synthetic" ? "disabled" : ""}`}>
          <input
            checked={download}
            disabled={name === "synthetic"}
            type="checkbox"
            onChange={(event) => setDownload(event.target.checked)}
          />
          <span>
            Download if missing
            <small>Requires AISHIELD_ALLOW_PUBLIC_DOWNLOADS=true</small>
          </span>
        </label>
      </div>
      <div className="policy-note">
        <Icon name="shield" />
        <p>
          Arbitrary URLs are never accepted. Public adapters use fixed canonical sources; Signal-10
          is deterministic synthetic data and is not a security benchmark.
        </p>
      </div>
      <div className="dialog-actions">
        <button className="button ghost" type="button" onClick={onCancel}>
          Cancel
        </button>
        <button className="button primary" disabled={busy} type="submit">
          <Icon name="database" size={16} />
          {busy ? "Loading dataset…" : "Load dataset"}
        </button>
      </div>
    </form>
  );
}
