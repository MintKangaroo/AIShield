import { type FormEvent, useState } from "react";

import { Icon } from "../components/Icon";
import { readApiKey } from "../apiKey";

export function ApiKeyForm({
  busy,
  onCancel,
  onClear,
  onSubmit,
}: {
  busy: boolean;
  onCancel: () => void;
  onClear: () => void;
  onSubmit: (key: string) => Promise<void>;
}) {
  const [key, setKey] = useState("");
  const stored = readApiKey();

  function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = key.trim();
    if (trimmed) {
      void onSubmit(trimmed);
    }
  }

  return (
    <form className="form-grid" onSubmit={submit}>
      <label>
        <span>API key</span>
        <input
          autoComplete="off"
          autoFocus
          placeholder={stored ? "A key is stored; enter a new one to replace it" : "Paste the key"}
          type="password"
          value={key}
          onChange={(event) => setKey(event.target.value)}
        />
        <small className="field-hint">
          Sent as an <code>X-API-Key</code> header. A Bearer token is also accepted.
        </small>
      </label>
      <div className="policy-note">
        <Icon name="shield" />
        <p>
          The key is kept in this browser tab only and is cleared when the tab closes. It is
          never written to a URL, so it cannot leak into proxy or server logs.
        </p>
      </div>
      <div className="dialog-actions">
        {stored && (
          <button className="button ghost" type="button" onClick={onClear}>
            Forget stored key
          </button>
        )}
        <button className="button ghost" type="button" onClick={onCancel}>
          Cancel
        </button>
        <button className="button primary" disabled={!key.trim() || busy} type="submit">
          <Icon name="check" size={16} />
          {busy ? "Checking…" : "Use this key"}
        </button>
      </div>
    </form>
  );
}
