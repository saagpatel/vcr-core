"""Byte-faithful cassette serialization and dependency-free validation."""

import base64
import binascii
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from .termination import Termination, _keys, _mapping

FORMAT_TAG = "vcr-partial-stream/v1"
CassetteClass = Literal["split_codepoint", "partial_event", "early_close"]


@dataclass(frozen=True)
class Chunk:
    index: int
    data: bytes


@dataclass(frozen=True)
class PartialCassette:
    id: str
    cls: CassetteClass
    description: str
    request: dict[str, str]
    status: int
    headers: tuple[tuple[str, str], ...]
    chunks: tuple[Chunk, ...]
    termination: Termination
    expect: dict[str, object] | None = None

    def body(self) -> bytes:
        return b"".join(chunk.data for chunk in self.chunks)

    def to_dict(self) -> dict[str, object]:
        doc: dict[str, object] = {
            "format": FORMAT_TAG,
            "id": self.id,
            "class": self.cls,
            "description": self.description,
            "request": dict(self.request),
            "response": {"status": self.status, "headers": [list(pair) for pair in self.headers]},
            "chunks": [
                {"index": chunk.index, "b64": base64.b64encode(chunk.data).decode("ascii")}
                for chunk in self.chunks
            ],
            "termination": self.termination.to_dict(),
            "body_sha256": hashlib.sha256(self.body()).hexdigest(),
        }
        if self.expect is not None:
            doc["expect"] = self.expect
        return doc

    @classmethod
    def from_dict(cls, d: object) -> "PartialCassette":
        doc = _mapping(d, "cassette")
        _keys(
            doc,
            {
                "format",
                "id",
                "class",
                "description",
                "request",
                "response",
                "chunks",
                "termination",
                "body_sha256",
            },
            {"expect"},
            "cassette",
        )
        if doc["format"] != FORMAT_TAG:
            raise ValueError("wrong cassette format tag")
        for key in ("id", "description"):
            if not isinstance(doc[key], str):
                raise ValueError(f"{key} must be a string")
        kind = doc["class"]
        if kind not in ("split_codepoint", "partial_event", "early_close"):
            raise ValueError("invalid cassette class")
        request = _mapping(doc["request"], "request")
        _keys(request, {"method", "url"}, set(), "request")
        if not all(isinstance(value, str) for value in request.values()):
            raise ValueError("request method and url must be strings")
        response = _mapping(doc["response"], "response")
        _keys(response, {"status", "headers"}, set(), "response")
        status = response["status"]
        if type(status) is not int:
            raise ValueError("response.status must be an integer")
        raw_headers = response["headers"]
        if not isinstance(raw_headers, list):
            raise ValueError("response.headers must be a list of pairs")
        headers: list[tuple[str, str]] = []
        for pair in raw_headers:
            if (
                not isinstance(pair, list)
                or len(pair) != 2
                or not isinstance(pair[0], str)
                or not isinstance(pair[1], str)
            ):
                raise ValueError("each header must be a pair of strings")
            headers.append((pair[0], pair[1]))
        raw_chunks = doc["chunks"]
        if not isinstance(raw_chunks, list):
            raise ValueError("chunks must be a list")
        chunks: list[Chunk] = []
        for index, value in enumerate(raw_chunks):
            chunk = _mapping(value, "chunk")
            _keys(chunk, {"index", "b64"}, set(), "chunk")
            if type(chunk["index"]) is not int or chunk["index"] != index:
                raise ValueError("chunk index must be contiguous starting at zero")
            encoded = chunk["b64"]
            if not isinstance(encoded, str):
                raise ValueError("chunk b64 must be a string")
            try:
                data = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ValueError("invalid chunk base64") from exc
            if base64.b64encode(data).decode("ascii") != encoded:
                raise ValueError("chunk base64 must use standard canonical encoding")
            chunks.append(Chunk(index, data))
        termination = Termination.from_dict(doc["termination"])
        if termination.after_chunk != len(chunks) - 1:
            raise ValueError("termination.after_chunk must match the last chunk index")
        digest = hashlib.sha256(b"".join(chunk.data for chunk in chunks)).hexdigest()
        if doc["body_sha256"] != digest:
            raise ValueError("body_sha256 mismatch")
        expect = _mapping(doc["expect"], "expect") if "expect" in doc else None
        # expect is arbitrary fixture-specific JSON; it must be JSON-native so that
        # load(dump(c)) == c holds exactly (no key coercion, no tuple-to-list drift).
        if expect is not None:
            _check_json(expect, "expect")
        return cls(
            cast("str", doc["id"]),
            kind,
            cast("str", doc["description"]),
            cast("dict[str, str]", request),
            status,
            tuple(headers),
            tuple(chunks),
            termination,
            expect,
        )


def _check_json(value: object, path: str) -> None:
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError(f"{path} must not contain NaN or infinity")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _check_json(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} keys must be strings")
            _check_json(item, f"{path}.{key}")
        return
    raise ValueError(f"{path} must contain only JSON values, got {type(value).__name__}")


def validate_partial(doc: object) -> None:
    PartialCassette.from_dict(doc)


def load(path_or_text: Path | str) -> PartialCassette:
    text = (
        path_or_text.read_text(encoding="utf-8") if isinstance(path_or_text, Path) else path_or_text
    )
    try:
        doc: object = json.loads(text)
    except (ValueError, RecursionError) as exc:
        raise ValueError("invalid cassette JSON") from exc
    return PartialCassette.from_dict(doc)


def dump(c: PartialCassette) -> str:
    doc = c.to_dict()
    validate_partial(doc)
    return json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
