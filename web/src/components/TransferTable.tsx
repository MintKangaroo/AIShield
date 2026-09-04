import { formatDate, formatPercent } from "../format";
import type { DatasetRecord, ModelVersionRecord, TransferRunRecord } from "../types";
import { Icon } from "./Icon";

export function TransferTable({
  datasets,
  models,
  transfers,
}: {
  datasets: DatasetRecord[];
  models: ModelVersionRecord[];
  transfers: TransferRunRecord[];
}) {
  if (!transfers.length) {
    return (
      <div className="empty-panel">
        <span className="empty-icon transfer">
          <Icon name="transfer" size={22} />
        </span>
        <h3>아직 블랙박스 전이 증거가 없습니다</h3>
        <p>
          Generate perturbations on a surrogate model and measure how many survive against a
          different target model.
        </p>
      </div>
    );
  }

  return (
    <div className="transfer-table">
      <div className="transfer-head">
        <span>전이</span>
        <span>Surrogate → target</span>
        <span>clean</span>
        <span>전이 robust</span>
        <span>전이 성공</span>
        <span>경계</span>
      </div>
      {transfers.map((transfer, index) => {
        const dataset = datasets.find((item) => item.id === transfer.dataset_id);
        const surrogate = models.find(
          (item) => item.id === transfer.surrogate_model_version_id,
        );
        const target = models.find((item) => item.id === transfer.target_model_version_id);
        return (
          <div className="transfer-row" key={transfer.id}>
            <span className="attack-name">
              <i>{transfer.attack.algorithm.toUpperCase()}</i>
              <span>
                <b>TR-{String(transfers.length - index).padStart(3, "0")}</b>
                <small>{formatDate(transfer.created_at)}</small>
              </span>
            </span>
            <span className="target-cell">
              <b>
                {surrogate?.architecture ?? "Unknown"} → {target?.architecture ?? "Unknown"}
              </b>
              <small>{dataset?.name.toUpperCase() ?? "알 수 없는 데이터셋"}</small>
            </span>
            <span className="mono">{formatPercent(transfer.metrics.clean_accuracy)}</span>
            <strong className="robust-value">
              {formatPercent(transfer.metrics.transferred_robust_accuracy)}
            </strong>
            <span className="mono">
              {formatPercent(transfer.metrics.transfer_attack_success_rate)}
              <small className="faint">
                {" "}
                ({transfer.metrics.successful_transfers}/{transfer.metrics.clean_correct_samples})
              </small>
            </span>
            <span className="bound-chip">
              ε {Math.round(transfer.attack.epsilon * 255)}/255
            </span>
          </div>
        );
      })}
    </div>
  );
}
