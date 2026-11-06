"""A TestClient wrapper that remembers every request it made.

The point is the failure path: when a test goes red, the first question is always
"what exactly did we send and what came back". The wrapper records each call and
the reporting hook in conftest.py attaches those records to the test report.

Nothing is printed on a green run, so ordinary output stays readable.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RecordedCall:
    method: str
    path: str
    status: int
    request_body: Any = None
    response_body: Any = None


@dataclass
class ApiClient:
    """Thin proxy over TestClient: same interface, plus recording."""

    transport: Any
    calls: list[RecordedCall] = field(default_factory=list)

    def _call(self, method: str, path: str, **kwargs):
        response = getattr(self.transport, method)(path, **kwargs)

        request_body = kwargs.get("json")
        try:
            response_body = response.json()
        except ValueError:
            response_body = response.text[:2000]

        self.calls.append(
            RecordedCall(
                method=method.upper(),
                path=path,
                status=response.status_code,
                request_body=request_body,
                response_body=response_body,
            )
        )
        return response

    def get(self, path: str, **kwargs):
        return self._call("get", path, **kwargs)

    def post(self, path: str, **kwargs):
        return self._call("post", path, **kwargs)

    def put(self, path: str, **kwargs):
        return self._call("put", path, **kwargs)

    def patch(self, path: str, **kwargs):
        return self._call("patch", path, **kwargs)

    def delete(self, path: str, **kwargs):
        return self._call("delete", path, **kwargs)

    def __getattr__(self, name: str):
        """Anything not wrapped is passed straight through to TestClient."""
        return getattr(self.transport, name)

    def as_text(self) -> str:
        """A readable log of every call, used by the failure hook."""
        lines = []
        for call in self.calls:
            lines.append(f"{call.method} {call.path} -> {call.status}")
            if call.request_body is not None:
                lines.append(f"  sent:     {call.request_body}")
            lines.append(f"  received: {call.response_body}")
        return "\n".join(lines) or "(no calls recorded)"

