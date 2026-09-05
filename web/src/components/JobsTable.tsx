import { formatDate, formatDuration } from "../format";
import type { JobRecord } from "../types";
import { Icon } from "./Icon";

const statusIcon = {
  queued: "clock",
  running: "refresh",
  succeeded: "check",
  failed: "close",
} as const;

export function JobsTable({ jobs }: { jobs: JobRecord[] }) {
  if (!jobs.length) {
    return (
      <div className="empty-panel">
        <span className="empty-icon">
          <Icon name="clock" size={22} />
        </span>
        <h3>백그라운드 작업이 없습니다</h3>
        <p>API 워커를 막지 않고 실행하도록 적대적 학습을 큐잉하세요.</p>
      </div>
    );
  }

  return (
    <div className="jobs-table">
      <div className="jobs-head">
        <span>작업</span>
        <span>종류</span>
        <span>상태</span>
        <span>소요</span>
        <span>결과</span>
      </div>
      {jobs.map((job) => (
        <div className={`job-row ${job.status}`} key={job.id}>
          <span className="run-id">
            <b className="mono">{job.id.slice(0, 8)}</b>
            <small>{formatDate(job.created_at)}</small>
          </span>
          <span>{job.kind}</span>
          <span className={`job-status ${job.status}`}>
            <Icon name={statusIcon[job.status]} size={13} />
            {job.status === "failed" && job.attempts > 1 ? "dead-letter" : job.status}
            {job.attempts > 1 ? <small className="attempt-count"> ×{job.attempts}</small> : null}
          </span>
          <span className="mono">{formatDuration(job.started_at, job.finished_at)}</span>
          <span className="mono job-result">
            {job.error ? (
              <em className="job-error" title={job.error}>
                {job.error}
              </em>
            ) : job.result_id ? (
              job.result_id.slice(0, 8)
            ) : (
              "—"
            )}
          </span>
        </div>
      ))}
    </div>
  );
}
