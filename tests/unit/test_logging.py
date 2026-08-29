"""Contract for structured logs and request correlation."""

import json
import logging
from io import StringIO

from fastapi.testclient import TestClient

from aishield.api.main import create_app
from aishield.api.middleware import REQUEST_ID_HEADER
from aishield.core.config import Settings
from aishield.core.logging import JsonFormatter, configure_logging, request_context


def _record(**extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        name="aishield.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="run %s",
        args=("finished",),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_formatter_emits_one_json_object_with_extras() -> None:
    payload = json.loads(JsonFormatter().format(_record(run_id="abc", duration_ms=12.5)))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "aishield.test"
    assert payload["message"] == "run finished"
    assert payload["run_id"] == "abc"
    assert payload["duration_ms"] == 12.5
    assert "request_id" not in payload


def test_formatter_includes_the_bound_request_id() -> None:
    with request_context("req-1"):
        payload = json.loads(JsonFormatter().format(_record()))

    assert payload["request_id"] == "req-1"


def test_request_context_is_restored_after_use() -> None:
    with request_context("outer"):
        with request_context("inner"):
            assert json.loads(JsonFormatter().format(_record()))["request_id"] == "inner"
        assert json.loads(JsonFormatter().format(_record()))["request_id"] == "outer"

    assert "request_id" not in json.loads(JsonFormatter().format(_record()))


def test_formatter_serializes_unexpected_extra_types() -> None:
    payload = json.loads(JsonFormatter().format(_record(path=object())))

    assert isinstance(payload["path"], str)


def test_exception_records_carry_the_traceback() -> None:
    try:
        raise ValueError("gradient was flat")
    except ValueError:
        record = _record()
        record.exc_info = __import__("sys").exc_info()

    payload = json.loads(JsonFormatter().format(record))

    assert "ValueError: gradient was flat" in payload["exception"]


def test_configure_logging_replaces_existing_handlers() -> None:
    root = logging.getLogger()
    root.addHandler(logging.NullHandler())

    configure_logging("WARNING")

    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JsonFormatter)
    assert root.level == logging.WARNING


def test_api_echoes_a_generated_request_id() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert len(response.headers[REQUEST_ID_HEADER]) == 36


def test_api_reuses_a_well_formed_caller_request_id() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get(
            "/api/v1/health/live", headers={REQUEST_ID_HEADER: "trace-from-proxy"}
        )

    assert response.headers[REQUEST_ID_HEADER] == "trace-from-proxy"


def test_api_replaces_an_abusive_caller_request_id() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/api/v1/health/live", headers={REQUEST_ID_HEADER: "x" * 500})

    assert response.headers[REQUEST_ID_HEADER] != "x" * 500
    assert len(response.headers[REQUEST_ID_HEADER]) == 36


def test_request_logs_carry_the_correlation_id() -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("aishield.api.request")
    logger.addHandler(handler)
    try:
        with TestClient(create_app(Settings(environment="test"))) as client:
            client.get("/api/v1/health/live", headers={REQUEST_ID_HEADER: "trace-9"})
    finally:
        logger.removeHandler(handler)

    entries = [json.loads(line) for line in stream.getvalue().splitlines() if line]
    completed = [entry for entry in entries if entry["message"] == "request completed"]
    assert completed
    assert completed[-1]["request_id"] == "trace-9"
    assert completed[-1]["http_status"] == 200
    assert completed[-1]["http_path"] == "/api/v1/health/live"
    assert completed[-1]["duration_ms"] >= 0
