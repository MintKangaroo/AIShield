import { type FormEvent, useState } from "react";

import { Icon } from "../components/Icon";
import type { LlmRedTeamRequest, ProbeCategory } from "../types";

const CATEGORIES: Array<{ id: ProbeCategory; label: string; hint: string }> = [
  {
    id: "system_prompt_leak",
    label: "System-prompt leak",
    hint: "Can the model be made to reveal a secret planted in its instructions?",
  },
  {
    id: "instruction_override",
    label: "Instruction override",
    hint: "Does the model follow injected instructions that override its rules?",
  },
  {
    id: "jailbreak",
    label: "Jailbreak framing",
    hint: "Do roleplay / hypothetical / developer-mode framings bypass a refusal?",
  },
];

export function LlmRedTeamForm({
  busy,
  onCancel,
  onSubmit,
}: {
  busy: boolean;
  onCancel: () => void;
  onSubmit: (payload: LlmRedTeamRequest) => Promise<void>;
}) {
  const [endpointUrl, setEndpointUrl] = useState("");
  const [selected, setSelected] = useState<Set<ProbeCategory>>(
    new Set(CATEGORIES.map((category) => category.id)),
  );
  const [retainText, setRetainText] = useState(false);
  const [authHeader, setAuthHeader] = useState("");
  const [authValue, setAuthValue] = useState("");
  const [authorized, setAuthorized] = useState(false);

  function toggle(category: ProbeCategory) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const payload: LlmRedTeamRequest = {
      endpoint_url: endpointUrl.trim(),
      authorized,
      categories: CATEGORIES.map((category) => category.id).filter((id) => selected.has(id)),
      max_probes: 50,
      seed: 1729,
      retain_text: retainText,
    };
    if (authHeader.trim() && authValue.trim()) {
      payload.auth_header = authHeader.trim();
      payload.auth_value = authValue.trim();
    }
    void onSubmit(payload);
  }

  const canSubmit = Boolean(endpointUrl.trim() && authorized && selected.size);

  return (
    <form className="form-grid" onSubmit={submit}>
      <label>
        <span>Target LLM endpoint URL</span>
        <input
          autoComplete="off"
          placeholder="http://llm.internal.example.com/chat"
          type="url"
          value={endpointUrl}
          onChange={(event) => setEndpointUrl(event.target.value)}
        />
        <small className="field-hint">
          Must be an allowlisted host accepting{" "}
          <code>{'{"system": "...", "prompt": "..."}'}</code> and returning{" "}
          <code>{'{"completion": "..."}'}</code>.
        </small>
      </label>

      <div className="probe-categories" role="group" aria-label="Probe categories">
        {CATEGORIES.map((category) => (
          <button
            className={selected.has(category.id) ? "active" : ""}
            key={category.id}
            type="button"
            onClick={() => toggle(category.id)}
          >
            <span>{category.label}</span>
            <small>{category.hint}</small>
          </button>
        ))}
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

      <label className="check-field">
        <input
          checked={retainText}
          type="checkbox"
          onChange={(event) => setRetainText(event.target.checked)}
        />
        <span>
          Retain prompt and completion text
          <small>
            Off by default — only SHA-256 fingerprints and verdicts are stored, since responses
            can carry sensitive content.
          </small>
        </span>
      </label>

      <label className="check-field authorize">
        <input
          checked={authorized}
          type="checkbox"
          onChange={(event) => setAuthorized(event.target.checked)}
        />
        <span>
          I am authorized to red-team this LLM.
          <small>The server also enforces its own host allowlist; both must hold or it returns 403.</small>
        </span>
      </label>

      <div className="policy-note attack-note">
        <Icon name="shield" />
        <p>
          Probes are diagnostic and benign: the &quot;forbidden&quot; content is a harmless planted
          token, so a successful jailbreak only ever reveals that token. This measures whether your
          model yields to a technique — it is not a source of working attacks.
        </p>
      </div>

      <div className="dialog-actions">
        <button className="button ghost" type="button" onClick={onCancel}>
          Cancel
        </button>
        <button className="button primary" disabled={!canSubmit || busy} type="submit">
          <Icon name="shield" size={16} />
          {busy ? "Probing target…" : "Run red-team"}
        </button>
      </div>
    </form>
  );
}
