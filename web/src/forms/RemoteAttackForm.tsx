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
        <span>대상 엔드포인트 URL</span>
        <input
          autoComplete="off"
          placeholder="http://model.internal.example.com/score"
          type="url"
          value={endpointUrl}
          onChange={(event) => setEndpointUrl(event.target.value)}
        />
        <small className="field-hint">
          이미지 배치에 대해 <code>{"{\"scores\": [[...]]}"}</code>를 반환하는 allowlist 호스트여야 합니다.
          데이터셋의 클래스 수가 기대 출력 크기로 전송됩니다.
        </small>
      </label>
      <label>
        <span>점검 데이터셋</span>
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
          <span>질의 예산</span>
          <input
            max={100000}
            min={1}
            type="number"
            value={maxQueries}
            onChange={(event) => setMaxQueries(Number(event.target.value))}
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
      <label className="check-field authorize">
        <input
          checked={authorized}
          type="checkbox"
          onChange={(event) => setAuthorized(event.target.checked)}
        />
        <span>
          이 대상에 대해 적대적 테스트를 수행할 권한이 있습니다.
          <small>
            서버는 설정된 allowlist에 없는 호스트도 거부합니다. 둘 다 충족해야 하며, 아니면 403으로 거부됩니다.
          </small>
        </span>
      </label>
      <div className="policy-note attack-note">
        <Icon name="shield" />
        <p>
          이것은 질의 전용 블랙박스 공격입니다: 이미지를 보내고 score를 읽을 뿐, 가중치나 그래디언트는 보지 않습니다. 모든 질의가 계수·보고되며, 위 자격 증명은 대상에게만 전송되고 기록된 증거에는 저장되지 않습니다.
        </p>
      </div>
      <div className="dialog-actions">
        <button className="button ghost" type="button" onClick={onCancel}>
          취소
        </button>
        <button className="button primary" disabled={!canSubmit || busy} type="submit">
          <Icon name="spark" size={16} />
          {busy ? "대상 질의 중…" : "블랙박스 공격 실행"}
        </button>
      </div>
    </form>
  );
}
