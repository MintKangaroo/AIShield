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
        <h3>No background jobs</h3>
        <p>Queue an adversarial training run to execute it without blocking the API worker.</p>
      </div>
    );
  }

  return (
    <div className="jobs-table">
      <div className="jobs-head">
        <span>Job</span>
        <span>Kind</span>
        <span>Status</span>
        <span>Duration</span>
        <span>Result</span>
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
            {job.status}
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
