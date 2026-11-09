"""Record sync and async byte streams without changing their boundaries."""

import codecs
from collections.abc import AsyncIterable, Iterable, Sequence
from typing import Literal

from .cassette import CassetteClass, Chunk, PartialCassette, validate_partial
from .termination import Termination, _keys, _mapping

Framing = Literal["sse", "ndjson", "raw"]


def record(
    chunks: Sequence[bytes],
    termination: Termination,
    *,
    id: str,
    cls: CassetteClass,
    description: str,
    request: dict[str, str],
    status: int = 200,
    headers: Sequence[tuple[str, str]] = (),
    expect: dict[str, object] | None = None,
) -> PartialCassette:
    _keys(_mapping(request, "request"), {"method", "url"}, set(), "request")
    for chunk in chunks:
        _check_chunk(chunk)
    cassette = PartialCassette(
        id,
        cls,
        description,
        dict(request),
        status,
        tuple(headers),
        tuple(Chunk(index, data) for index, data in enumerate(chunks)),
        termination,
        expect,
    )
    validate_partial(cassette.to_dict())
    return cassette


def _check_chunk(chunk: object) -> None:
    if not isinstance(chunk, bytes):
        raise ValueError("source chunks must be bytes")


def _check_framing(framing: Framing) -> None:
    if framing not in ("sse", "ndjson", "raw"):
        raise ValueError("framing must be sse, ndjson, or raw")


def _finished(chunks: list[bytes], framing: Framing) -> Termination:
    body = b"".join(chunks)
    detail: str | None = None
    # surrogateescape preserves malformed bytes while still buffering an incomplete
    # trailing UTF-8 sequence. No decoding result is ever used as recorded data.
    decoder = codecs.getincrementaldecoder("utf-8")("surrogateescape")
    decoder.decode(body, final=False)
    if decoder.getstate()[0]:
        detail = "incomplete UTF-8 sequence at end of body"
    elif body and framing == "sse" and not body.endswith(b"\n\n"):
        detail = "incomplete SSE event: body does not end with a blank line"
    elif body and framing == "ndjson" and not body.endswith(b"\n"):
        detail = "incomplete NDJSON unit: body does not end with a newline"
    return Termination(
        "clean_close" if detail is None else "truncated_mid_event",
        len(chunks) - 1,
        detail=detail,
    )


def record_iter(
    source: Iterable[bytes],
    *,
    framing: Framing = "raw",
    id: str,
    cls: CassetteClass,
    description: str,
    request: dict[str, str],
    status: int = 200,
    headers: Sequence[tuple[str, str]] = (),
    expect: dict[str, object] | None = None,
) -> PartialCassette:
    _check_framing(framing)
    chunks: list[bytes] = []
    try:
        for chunk in source:
            _check_chunk(chunk)
            chunks.append(chunk)
    except OSError as exc:
        termination = Termination("early_close", len(chunks) - 1, error=type(exc).__name__)
    else:
        termination = _finished(chunks, framing)
    return record(
        chunks,
        termination,
        id=id,
        cls=cls,
        description=description,
        request=request,
        status=status,
        headers=headers,
        expect=expect,
    )


async def arecord_iter(
    source: AsyncIterable[bytes],
    *,
    framing: Framing = "raw",
    id: str,
    cls: CassetteClass,
    description: str,
    request: dict[str, str],
    status: int = 200,
    headers: Sequence[tuple[str, str]] = (),
    expect: dict[str, object] | None = None,
) -> PartialCassette:
    _check_framing(framing)
    chunks: list[bytes] = []
    try:
        async for chunk in source:
            _check_chunk(chunk)
            chunks.append(chunk)
    except OSError as exc:
        termination = Termination("early_close", len(chunks) - 1, error=type(exc).__name__)
    else:
        termination = _finished(chunks, framing)
    return record(
        chunks,
        termination,
        id=id,
        cls=cls,
        description=description,
        request=request,
        status=status,
        headers=headers,
        expect=expect,
    )
