import { type FormEvent, useState } from "react";

import { Icon } from "../components/Icon";
import { parseSampleCap } from "../hooks/useCompatibleModels";
import type { DatasetRecord, RemoteAttackRequest } from "../types";

export function RemoteAttackForm({
  busy,
  datasets,
  onCancel,
  onSubmit,
}: {
  busy: boolean;
  datasets: DatasetRecord[];
  onCancel: () => void;
  onSubmit: (payload: RemoteAttackRequest) => Promise<void>;
}) {
  const [datasetId, setDatasetId] = useState(datasets[0]?.id ?? "");
  const dataset = datasets.find((item) => item.id === datasetId);
  const [endpointUrl, setEndpointUrl] = useState("");
  const [epsilon, setEpsilon] = useState(8);
  const [maxQueries, setMaxQueries] = useState(5000);
  const [maxSamples, setMaxSamples] = useState("256");
  const [authHeader, setAuthHeader] = useState("");
  const [authValue, setAuthValue] = useState("");
  const [authorized, setAuthorized] = useState(false);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!dataset) return;
    const payload: RemoteAttackRequest = {
      endpoint_url: endpointUrl.trim(),
      num_classes: dataset.num_classes,
      dataset_id: datasetId,
      authorized,
      epsilon: epsilon / 255,
      max_queries: maxQueries,
      seed: 1729,
      batch_size: 64,
      max_samples: parseSampleCap(maxSamples),
    };
    if (authHeader.trim() && authValue.trim()) {
      payload.auth_header = authHeader.trim();
      payload.auth_value = authValue.trim();
    }
    void onSubmit(payload);
  }

  const canSubmit = Boolean(datasetId && endpointUrl.trim() && authorized);

  return (
    <form className="form-grid" onSubmit={submit}>
      <label>
        <span>Target endpoint URL</span>
        <input
          autoComplete="off"
          placeholder="http://model.internal.example.com/score"
          type="url"
          value={endpointUrl}
          onChange={(event) => setEndpointUrl(event.target.value)}
        />
        <small className="field-hint">
          Must be an allowlisted host that returns <code>{"{\"scores\": [[...]]}"}</code> for a
          batch of images. The dataset&apos;s class count is sent as the expected output size.
        </small>
      </label>
      <label>
        <span>Probe dataset</span>
        <select value={datasetId} onChange={(event) => setDatasetId(event.target.value)}>
          {datasets.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name.toUpperCase()} · {item.split} · {item.num_classes} classes
            </option>
          ))}
        </select>
      </label>
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
          <span>Query budget</span>
          <input
            max={100000}
            min={1}
            type="number"
            value={maxQueries}
            onChange={(event) => setMaxQueries(Number(event.target.value))}
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
          <span>Auth header (optional)</span>
          <input
            autoComplete="off"
            placeholder="Authorization"
            value={authHeader}
            onChange={(event) => setAuthHeader(event.target.value)}
          />
        </label>
        <label>
          <span>Auth value (optional)</span>
          <input
            autoComplete="off"
            placeholder="Bearer …"
            type="password"
            value={authValue}
            onChange={(event) => setAuthValue(event.target.value)}
          />
        </label>
      </div>
      <label className="check-field authorize">
        <input
          checked={authorized}
          type="checkbox"
          onChange={(event) => setAuthorized(event.target.checked)}
        />
        <span>
          I am authorized to run adversarial tests against this target.
          <small>
            The server also refuses any host that is not in its configured allowlist. Both must
            hold, or the request is rejected with 403.
          </small>
        </span>
      </label>
      <div className="policy-note attack-note">
        <Icon name="shield" />
        <p>
          This is a query-only black-box attack: it sends images and reads scores, never weights or
          gradients. Every query is counted and reported, and the credential above is sent only to
          the target — it is never stored in the recorded evidence.
        </p>
      </div>
      <div className="dialog-actions">
        <button className="button ghost" type="button" onClick={onCancel}>
          Cancel
        </button>
        <button className="button primary" disabled={!canSubmit || busy} type="submit">
          <Icon name="spark" size={16} />
          {busy ? "Querying target…" : "Run black-box attack"}
        </button>
      </div>
    </form>
  );
}
