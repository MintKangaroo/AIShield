"""Run evaluation work in a separate process from the API.

The API process answers requests; this process does the heavy torch work. They
share nothing but the metadata store and the job broker, so a worker can be
given its own CPU, memory and device budget without the API competing for them.

A worker rebuilds the model and dataset handles it needs from stored metadata,
the same way a restarted API does, and verifies their content hashes before
running. It therefore cannot evaluate against inputs that changed underneath the
recorded identity.
"""

import argparse
import logging
import signal
import sys
from collections.abc import Sequence
from types import FrameType

from aishield.core.config import Settings, get_settings
from aishield.core.logging import configure_logging, request_context
from aishield.jobs.redis_queue import RedisJobQueue
from aishield.registry.errors import RegistryError
from aishield.registry.service import RegistryService

logger = logging.getLogger("aishield.worker")


class Worker:
    """Claim tasks from the shared queue and execute them against the registry."""

    def __init__(self, settings: Settings, *, poll_timeout: int = 5) -> None:
        self.settings = settings
        self.poll_timeout = poll_timeout
        self.registry = RegistryService(settings)
        self.queue = RedisJobQueue(
            settings.redis_url,
            max_pending=settings.job_max_pending,
            retained_jobs=settings.job_retained_records,
            observer=self.registry.record_job,
        )
        self._stopping = False

    def stop(self) -> None:
        """Ask the loop to finish the current task and exit."""

        self._stopping = True

    def prepare(self) -> None:
        """Rebuild registry state from stored metadata before claiming any work."""

        summary = self.registry.replay_journal()
        logger.info(
            "worker ready",
            extra={
                "metadata_backend": self.settings.metadata_backend,
                "datasets_restored": summary.datasets_restored,
                "models_restored": summary.models_restored,
                "skipped": len(summary.skipped),
            },
        )

    def run_once(self) -> bool:
        """Claim and execute at most one task. Returns False when nothing was ready."""

        claimed = self.queue.claim(timeout=self.poll_timeout)
        if claimed is None:
            return False
        job, task = claimed
        with request_context(f"job-{job.id}"):
            try:
                # A worker may be newer than the state it replayed at start-up, so
                # refresh before running rather than failing on a handle it lacks.
                self.registry.replay_journal()
                result_id = self.registry.execute_task(task)
            except Exception as error:  # noqa: BLE001 - persist failure as job evidence
                logger.exception("task failed", extra={"job_id": str(job.id)})
                self.queue.fail(job.id, str(error), task=task)
            else:
                self.queue.complete(job.id, result_id)
        self.queue.evict_finished()
        return True

    def run_forever(self) -> int:
        """Consume tasks until asked to stop."""

        self.prepare()
        while not self._stopping:
            try:
                self.run_once()
            except RegistryError:
                # A broker or database blip must not kill the worker; the next
                # claim retries, and an unrecoverable outage shows up as repeated
                # logged failures rather than a silent exit.
                logger.exception("worker loop error")
        logger.info("worker stopped")
        return 0

    def close(self) -> None:
        self.queue.shutdown()
        self.registry.shutdown()


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for ``aishield-worker``."""

    parser = argparse.ArgumentParser(prog="aishield-worker", description=__doc__)
    parser.add_argument(
        "--poll-timeout",
        type=int,
        default=5,
        help="seconds to block waiting for work before checking for shutdown",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="execute at most one task and exit (useful in tests and CI)",
    )
    arguments = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level)
    worker = Worker(settings, poll_timeout=arguments.poll_timeout)

    def handle_signal(number: int, frame: FrameType | None) -> None:
        logger.info("shutdown requested", extra={"signal": number})
        worker.stop()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        if arguments.once:
            worker.prepare()
            return 0 if worker.run_once() else 1
        return worker.run_forever()
    finally:
        worker.close()


if __name__ == "__main__":  # pragma: no cover - module entry point
    sys.exit(main())
