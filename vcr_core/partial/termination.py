"""Explicit transport and framing outcomes for recorded streams."""

from dataclasses import dataclass
from typing import Literal, cast

TerminationState = Literal["clean_close", "early_close", "truncated_mid_event"]


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object with string keys")
    return cast("dict[str, object]", value)


def _keys(doc: dict[str, object], required: set[str], optional: set[str], label: str) -> None:
    missing = required - doc.keys()
    extra = doc.keys() - required - optional
    if missing or extra:
        raise ValueError(f"{label}: missing keys {sorted(missing)}, unknown keys {sorted(extra)}")


@dataclass(frozen=True)
class Termination:
    state: TerminationState
    after_chunk: int
    error: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, object]:
        doc: dict[str, object] = {"state": self.state, "after_chunk": self.after_chunk}
        if self.error is not None:
            doc["error"] = self.error
        if self.detail is not None:
            doc["detail"] = self.detail
        return doc

    @classmethod
    def from_dict(cls, d: object) -> "Termination":
        doc = _mapping(d, "termination")
        _keys(doc, {"state", "after_chunk"}, {"error", "detail"}, "termination")
        state = doc["state"]
        if state not in ("clean_close", "early_close", "truncated_mid_event"):
            raise ValueError("termination.state is invalid")
        after = doc["after_chunk"]
        if type(after) is not int or after < -1:
            raise ValueError("termination.after_chunk must be an integer >= -1")
        error = doc.get("error")
        if "error" in doc and (not isinstance(error, str) or not error):
            raise ValueError("termination.error must be a non-empty string")
        if state == "early_close" and error is None:
            raise ValueError("early_close requires error")
        if state == "clean_close" and "error" in doc:
            raise ValueError("clean_close forbids error")
        detail = doc.get("detail")
        if "detail" in doc and not isinstance(detail, str):
            raise ValueError("termination.detail must be a string")
        return cls(state, after, cast("str | None", error), cast("str | None", detail))
