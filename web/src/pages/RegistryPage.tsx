import { Icon } from "../components/Icon";
import { shortHash } from "../format";
import type { DatasetRecord, ModelVersionRecord } from "../types";

export function RegistryPage({
  datasets,
  models,
  onOpenDataset,
  onOpenModel,
}: {
  datasets: DatasetRecord[];
  models: ModelVersionRecord[];
  onOpenDataset: () => void;
  onOpenModel: () => void;
}) {
  return (
    <div className="page-content registry-content">
      <section className="registry-summary">
        <div>
          <span className="summary-icon">
            <Icon name="shield" size={26} />
          </span>
          <div>
            <h2>신뢰 런타임 인벤토리</h2>
            <p>
              불변 정체성을 가진 프로세스 로컬 핸들. 파일은 설정된 저장소에 콘텐츠 주소로 남습니다.
            </p>
          </div>
        </div>
        <span className="policy-pill">
          <i /> External downloads{" "}
          {datasets.some((item) => item.source === "approved_public") ? "사용 중" : "제한됨"}
        </span>
      </section>

      <section className="panel registry-section">
        <div className="panel-heading">
          <div>
            <span className="kicker">입력 출처</span>
            <h3>데이터셋</h3>
          </div>
          <button className="button secondary compact" type="button" onClick={onOpenDataset}>
            <Icon name="plus" size={15} /> 데이터셋 적재
          </button>
        </div>
        <div className="registry-grid">
          {datasets.map((dataset) => (
            <article className="registry-card" key={dataset.id}>
              <div className="registry-card-top">
                <span className="registry-icon dataset">
                  <Icon name="database" />
                </span>
                <span className={`source-badge ${dataset.source}`}>
                  {dataset.source === "generated" ? "생성됨" : "승인된 공개"}
                </span>
              </div>
              <h4>{dataset.name.toUpperCase()}</h4>
              <p>{dataset.version}</p>
              <dl>
                <div>
                  <dt>Split</dt>
                  <dd>{dataset.split}</dd>
                </div>
                <div>
                  <dt>샘플 수</dt>
                  <dd>{dataset.sample_count.toLocaleString()}</dd>
                </div>
                <div>
                  <dt>형태</dt>
                  <dd>{dataset.input_shape.join(" × ")}</dd>
                </div>
                <div>
                  <dt>클래스</dt>
                  <dd>{dataset.num_classes}</dd>
                </div>
              </dl>
              <div className="card-hash">
                <Icon name="fingerprint" size={14} />
                <code>{shortHash(dataset.manifest_sha256)}</code>
              </div>
            </article>
          ))}
          {!datasets.length && (
            <button className="add-card" type="button" onClick={onOpenDataset}>
              <span>
                <Icon name="plus" />
              </span>
              <b>첫 데이터셋 적재</b>
              <small>Signal-10은 다운로드 없이 동작합니다.</small>
            </button>
          )}
        </div>
      </section>

      <section className="panel registry-section">
        <div className="panel-heading">
          <div>
            <span className="kicker">모델 무결성</span>
            <h3>모델 버전</h3>
          </div>
          <button
            className="button secondary compact"
            disabled={!datasets.length}
            type="button"
            onClick={onOpenModel}
          >
            <Icon name="plus" size={15} /> 모델 생성
          </button>
        </div>
        <div className="registry-grid">
          {models.map((model) => (
            <article className="registry-card" key={model.id}>
              <div className="registry-card-top">
                <span className="registry-icon model">
                  <Icon name="layers" />
                </span>
                <span className="source-badge generated">{model.device.toUpperCase()}</span>
              </div>
              <h4>{model.name}</h4>
              <p>
                {model.architecture} · seed {model.seed}
              </p>
              <dl>
                <div>
                  <dt>파라미터</dt>
                  <dd>{model.parameter_count.toLocaleString()}</dd>
                </div>
                <div>
                  <dt>클래스</dt>
                  <dd>{model.num_classes}</dd>
                </div>
                <div>
                  <dt>채널</dt>
                  <dd>{model.input_channels}</dd>
                </div>
                <div>
                  <dt>출처</dt>
                  <dd>{model.source === "trained" ? "학습됨" : "초기화됨"}</dd>
                </div>
              </dl>
              <div className="card-hash">
                <Icon name="fingerprint" size={14} />
                <code>{shortHash(model.state_dict_sha256)}</code>
              </div>
            </article>
          ))}
          {!models.length && (
            <button
              className="add-card"
              disabled={!datasets.length}
              type="button"
              onClick={onOpenModel}
            >
              <span>
                <Icon name="plus" />
              </span>
              <b>첫 모델 생성</b>
              <small>결정론적 SmallCNN으로 시작하세요.</small>
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
