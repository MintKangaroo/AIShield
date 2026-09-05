"""HTTP client for an authorized remote image-classifier endpoint.

This is the boundary between the lab and a real deployed model: the attack never
sees weights or gradients, only the scores this client fetches over the network.
It speaks a small, explicit JSON contract and validates every response, so a
malformed or hostile reply becomes an error rather than corrupt evidence.

Authorization (allowlist + explicit confirmation) is enforced by the caller before
this client is ever constructed; the client only guards the transport itself.
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import urlparse

import torch
from torch import Tensor

from aishield.registry.errors import RegistryError

#: Endpoints must return this many scores per image and accept this contract.
#: request:  {"images": [[[[...]]]]}   # (N, C, H, W) floats in [0, 1]
#: response (scores mode): {"scores": [[...]]}   # (N, num_classes) floats
#: response (labels mode): {"labels": [...]}     # (N,) integer class indices
REQUEST_FORMAT = "aishield.image-scores.v1"


@dataclass(frozen=True)
class RemoteEndpoint:
    """A remote model the operator has declared and is authorized to test."""

    url: str
    num_classes: int
    # "scores" returns per-class scores (needed for the Square attack); "labels"
    # returns only the predicted class (a decision-only endpoint, the harder case).
    returns: str = "scores"
    timeout_seconds: float = 30.0
    # An optional bearer-style header for the operator's own endpoint auth. It is
    # sent to the target only and is never recorded in evidence.
    auth_header: str | None = None
    auth_value: str | None = field(default=None, repr=False)

    @property
    def host(self) -> str:
        return urlparse(self.url).hostname or ""


class RemoteImageClassifier:
    """Query a remote endpoint for class scores over a batch of images."""

    def __init__(self, endpoint: RemoteEndpoint) -> None:
        scheme = urlparse(endpoint.url).scheme
        if scheme not in {"http", "https"}:
            raise RegistryError("remote endpoint must be an http(s) URL")
        if endpoint.num_classes < 2:
            raise RegistryError("remote endpoint must expose at least two classes")
        if endpoint.returns not in {"scores", "labels"}:
            raise RegistryError("remote endpoint 'returns' must be 'scores' or 'labels'")
        self._endpoint = endpoint

    def _post(self, images: Tensor) -> bytes:
        if images.ndim != 4:
            raise RegistryError("remote request must be a (N, C, H, W) batch")
        payload = json.dumps(
            {"format": REQUEST_FORMAT, "images": images.detach().cpu().tolist()}
        ).encode("utf-8")
        request = urllib.request.Request(  # noqa: S310 - scheme validated in __init__
            self._endpoint.url,
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        if self._endpoint.auth_header and self._endpoint.auth_value:
            request.add_header(self._endpoint.auth_header, self._endpoint.auth_value)
        try:
            with urllib.request.urlopen(  # noqa: S310 - scheme validated in __init__
                request, timeout=self._endpoint.timeout_seconds
            ) as response:
                body: bytes = response.read()
                return body
        except (urllib.error.URLError, TimeoutError) as error:
            raise RegistryError(f"remote endpoint is unreachable: {error}") from error

    def score(self, images: Tensor) -> Tensor:
        """Return a ``(N, num_classes)`` score tensor for a batch in ``[0, 1]``."""

        return self._parse(self._post(images), expected_rows=int(images.shape[0]))

    def predict_labels(self, images: Tensor) -> Tensor:
        """Return a ``(N,)`` label tensor, from a labels endpoint or scores argmax."""

        body = self._post(images)
        if self._endpoint.returns == "labels":
            return self._parse_labels(body, expected_rows=int(images.shape[0]))
        return self._parse(body, expected_rows=int(images.shape[0])).argmax(dim=1)

    def _parse(self, body: bytes, *, expected_rows: int) -> Tensor:
        try:
            decoded = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise RegistryError("remote endpoint returned invalid JSON") from error
        if not isinstance(decoded, dict) or "scores" not in decoded:
            raise RegistryError("remote response must be an object with a 'scores' field")
        scores = decoded["scores"]
        if (
            not isinstance(scores, list)
            or len(scores) != expected_rows
            or not all(
                isinstance(row, list) and len(row) == self._endpoint.num_classes for row in scores
            )
            or not all(isinstance(value, int | float) for row in scores for value in row)
        ):
            raise RegistryError("remote response must be a (batch, num_classes) array of numbers")
        tensor = torch.tensor(scores, dtype=torch.float32)
        if not torch.isfinite(tensor).all():
            raise RegistryError("remote endpoint returned non-finite scores")
        return tensor

    def _parse_labels(self, body: bytes, *, expected_rows: int) -> Tensor:
        try:
            decoded = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise RegistryError("remote endpoint returned invalid JSON") from error
        if not isinstance(decoded, dict) or "labels" not in decoded:
            raise RegistryError("remote label response must be an object with a 'labels' field")
        labels = decoded["labels"]
        if (
            not isinstance(labels, list)
            or len(labels) != expected_rows
            or not all(isinstance(value, int) for value in labels)
            or not all(0 <= value < self._endpoint.num_classes for value in labels)
        ):
            raise RegistryError(
                "remote label response must be a length-N array of valid class indices"
            )
        return torch.tensor(labels, dtype=torch.long)
