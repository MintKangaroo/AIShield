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
#: response: {"scores":  [[...]]}      # (N, num_classes) floats
REQUEST_FORMAT = "aishield.image-scores.v1"


@dataclass(frozen=True)
class RemoteEndpoint:
    """A remote model the operator has declared and is authorized to test."""

    url: str
    num_classes: int
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
        self._endpoint = endpoint

    def score(self, images: Tensor) -> Tensor:
        """Return a ``(N, num_classes)`` score tensor for a batch in ``[0, 1]``."""

        if images.ndim != 4:
            raise RegistryError("remote score request must be a (N, C, H, W) batch")
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
                body = response.read()
        except (urllib.error.URLError, TimeoutError) as error:
            raise RegistryError(f"remote endpoint is unreachable: {error}") from error

        return self._parse(body, expected_rows=int(images.shape[0]))

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
