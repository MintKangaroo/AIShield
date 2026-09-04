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
        <span>API 키</span>
        <input
          autoComplete="off"
          autoFocus
          placeholder={stored ? "키가 저장되어 있습니다. 교체하려면 새 키를 입력하세요" : "Paste the key"}
          type="password"
          value={key}
          onChange={(event) => setKey(event.target.value)}
        />
        <small className="field-hint">
          <code>X-API-Key</code> 헤더로 전송합니다. Bearer 토큰도 허용됩니다.
        </small>
      </label>
      <div className="policy-note">
        <Icon name="shield" />
        <p>
          키는 이 브라우저 탭에만 보관되고 탭을 닫으면 지워집니다. URL에 기록되지 않으므로 프록시·서버 로그로 유출될 수 없습니다.
        </p>
      </div>
      <div className="dialog-actions">
        {stored && (
          <button className="button ghost" type="button" onClick={onClear}>
            저장된 키 삭제
          </button>
        )}
        <button className="button ghost" type="button" onClick={onCancel}>
          취소
        </button>
        <button className="button primary" disabled={!key.trim() || busy} type="submit">
          <Icon name="check" size={16} />
          {busy ? "확인 중…" : "이 키 사용"}
        </button>
      </div>
    </form>
  );
}
