"""Small bounded worker queue with a Redis-replaceable interface."""

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from threading import RLock
from uuid import UUID, uuid4

from aishield.jobs.contracts import JobRecord, JobStatus


class JobQueue:
    def __init__(self, max_workers: int = 2) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="aishield")
        self._jobs: dict[UUID, JobRecord] = {}
        self._lock = RLock()

    def submit(self, kind: str, task: Callable[[], UUID | None]) -> JobRecord:
        job = JobRecord.queued(uuid4(), kind)
        with self._lock:
            self._jobs[job.id] = job
        future = self._executor.submit(self._run, job.id, task)
        future.add_done_callback(lambda completed: self._finish(job.id, completed))
        return job

    def _run(self, job_id: UUID, task: Callable[[], UUID | None]) -> UUID | None:
        with self._lock:
            current = self._jobs[job_id]
            self._jobs[job_id] = current.model_copy(
                update={"status": JobStatus.RUNNING, "started_at": datetime.now(UTC)}
            )
        return task()

    def _finish(self, job_id: UUID, future: Future[UUID | None]) -> None:
        with self._lock:
            current = self._jobs[job_id]
            try:
                result_id = future.result()
                update: dict[str, object] = {
                    "status": JobStatus.SUCCEEDED,
                    "result_id": result_id,
                    "finished_at": datetime.now(UTC),
                }
            except Exception as error:  # noqa: BLE001 - persist worker failure as job evidence
                update = {
                    "status": JobStatus.FAILED,
                    "error": str(error),
                    "finished_at": datetime.now(UTC),
                }
            self._jobs[job_id] = current.model_copy(update=update)

    def get(self, job_id: UUID) -> JobRecord:
        with self._lock:
            return self._jobs[job_id]

    def list(self) -> list[JobRecord]:
        with self._lock:
            return [self._jobs[key] for key in sorted(self._jobs, key=str)]
