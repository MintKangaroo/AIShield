"""HTTP client for an authorized remote LLM endpoint.

Query-only, like the image client: it sends a system prompt and a user prompt and
reads back a completion. Authorization (allowlist + confirmation) is enforced by
the service before this is constructed; the client only guards the transport and
validates the response.
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import urlparse

from aishield.registry.errors import RegistryError

#: single turn:  {"format": "aishield.llm-chat.v1", "system": "...", "prompt": "..."}
#: multi turn:   {"format": "aishield.llm-chat.v1", "system": "...",
#:                "messages": [{"role": "user"|"assistant", "content": "..."}]}
#: response:     {"completion": "..."}
REQUEST_FORMAT = "aishield.llm-chat.v1"
#: Hard cap on a completion we will read, so a hostile endpoint cannot flood us.
MAX_COMPLETION_CHARS = 100_000


@dataclass(frozen=True)
class ChatMessage:
    """One turn of a conversation sent to the model."""

    role: str  # "user" or "assistant"
    content: str


@dataclass(frozen=True)
class LlmEndpoint:
    """A remote LLM the operator has declared and is authorized to test."""

    url: str
    timeout_seconds: float = 60.0
    auth_header: str | None = None
    auth_value: str | None = field(default=None, repr=False)

    @property
    def host(self) -> str:
        return urlparse(self.url).hostname or ""


class RemoteLlm:
    """Send one chat turn to a remote endpoint and return its completion."""

    def __init__(self, endpoint: LlmEndpoint) -> None:
        if urlparse(endpoint.url).scheme not in {"http", "https"}:
            raise RegistryError("remote LLM endpoint must be an http(s) URL")
        self._endpoint = endpoint

    def complete(self, system: str, prompt: str) -> str:
        """Return the model's completion for one (system, prompt) turn."""

        return self.chat(system, [ChatMessage("user", prompt)])

    def chat(self, system: str, messages: list["ChatMessage"]) -> str:
        """Return the model's completion given a conversation history.

        A single user turn is sent as ``prompt`` so a single-turn endpoint keeps
        working; multi-turn conversations are sent as ``messages``.
        """

        if not messages or messages[-1].role != "user":
            raise RegistryError("a chat turn must end with a user message")
        body_json: dict[str, object] = {"format": REQUEST_FORMAT, "system": system}
        if len(messages) == 1:
            body_json["prompt"] = messages[0].content
        else:
            body_json["messages"] = [{"role": m.role, "content": m.content} for m in messages]
        payload = json.dumps(body_json).encode("utf-8")
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
            raise RegistryError(f"remote LLM endpoint is unreachable: {error}") from error
        return self._parse(body)

    def _parse(self, body: bytes) -> str:
        try:
            decoded = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise RegistryError("remote LLM returned invalid JSON") from error
        if not isinstance(decoded, dict) or not isinstance(decoded.get("completion"), str):
            raise RegistryError("remote LLM response must be an object with a string 'completion'")
        completion: str = decoded["completion"]
        if len(completion) > MAX_COMPLETION_CHARS:
            raise RegistryError("remote LLM completion exceeded the size limit")
        return completion
