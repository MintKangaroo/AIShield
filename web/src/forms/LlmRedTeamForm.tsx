import { type FormEvent, useState } from "react";

import { Icon } from "../components/Icon";
import type { LlmRedTeamRequest, ProbeCategory } from "../types";

const CATEGORIES: Array<{ id: ProbeCategory; label: string; hint: string }> = [
  {
    id: "system_prompt_leak",
    label: "System-prompt 유출",
    hint: "명령에 심어둔 비밀을 모델이 드러내게 만들 수 있는가?",
  },
  {
    id: "instruction_override",
    label: "명령 override",
    hint: "모델이 규칙을 무시하는 주입 명령을 따르는가?",
  },
  {
    id: "jailbreak",
    label: "Jailbreak 프레이밍",
    hint: "roleplay·가정·developer-mode 프레이밍이 거부를 우회하는가?",
  },
  {
    id: "multi_turn",
    label: "Multi-turn",
    hint: "여러 턴에 걸쳐 서서히 유도한 뒤 비밀을 추출하는가? (대화 수준)",
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
        <span>대상 LLM 엔드포인트 URL</span>
        <input
          autoComplete="off"
          placeholder="http://llm.internal.example.com/chat"
          type="url"
          value={endpointUrl}
          onChange={(event) => setEndpointUrl(event.target.value)}
        />
        <small className="field-hint">
          <code>{'{"system": "...", "prompt": "..."}'}</code>를 받고{" "}
          <code>{'{"completion": "..."}'}</code>를 반환하는 allowlist 호스트여야 합니다.
        </small>
      </label>

      <div className="probe-categories" role="group" aria-label="점검 카테고리">
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
          <span>인증 헤더 (선택)</span>
          <input
            autoComplete="off"
            placeholder="Authorization"
            value={authHeader}
            onChange={(event) => setAuthHeader(event.target.value)}
          />
        </label>
        <label>
          <span>인증 값 (선택)</span>
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
          prompt·completion 텍스트 보존
          <small>
            기본 꺼짐 — 응답이 민감한 내용을 담을 수 있어 SHA-256 지문과 판정만 저장합니다.
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
          이 LLM을 레드팀할 권한이 있습니다.
          <small>서버는 자체 호스트 allowlist도 강제합니다. 둘 다 충족해야 하며 아니면 403을 반환합니다.</small>
        </span>
      </label>

      <div className="policy-note attack-note">
        <Icon name="shield" />
        <p>
          점검은 진단적이고 무해합니다: &quot;금지된&quot; 내용은 무해한 심어둔 토큰이라, 성공한 jailbreak도 그 토큰만 드러냅니다. 이는 모델이 기법에 굴복하는지 측정할 뿐, 실동작 공격의 출처가 아닙니다.
        </p>
      </div>

      <div className="dialog-actions">
        <button className="button ghost" type="button" onClick={onCancel}>
          취소
        </button>
        <button className="button primary" disabled={!canSubmit || busy} type="submit">
          <Icon name="shield" size={16} />
          {busy ? "대상 점검 중…" : "레드팀 실행"}
        </button>
      </div>
    </form>
  );
}
