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
        <span>데이터셋 어댑터</span>
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
            <option value="test">테스트</option>
            <option value="train">학습</option>
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
            없으면 다운로드
            <small>AISHIELD_ALLOW_PUBLIC_DOWNLOADS=true 필요</small>
          </span>
        </label>
      </div>
      <div className="policy-note">
        <Icon name="shield" />
        <p>
          임의 URL은 절대 허용되지 않습니다. 공개 어댑터는 고정된 표준 소스를 쓰며, Signal-10은 결정론적 합성 데이터로 보안 벤치마크가 아닙니다.
        </p>
      </div>
      <div className="dialog-actions">
        <button className="button ghost" type="button" onClick={onCancel}>
          취소
        </button>
        <button className="button primary" disabled={busy} type="submit">
          <Icon name="database" size={16} />
          {busy ? "데이터셋 적재 중…" : "데이터셋 적재"}
        </button>
      </div>
    </form>
  );
}
