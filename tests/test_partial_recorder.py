"""Recorders preserve yielded chunks and detect incomplete endings."""

import asyncio
from collections.abc import AsyncIterator, Iterator
from typing import Literal, TypedDict

import pytest

from vcr_core.partial import arecord_iter, record_iter


class RecordMetadata(TypedDict):
    id: str
    cls: Literal["split_codepoint", "partial_event", "early_close"]
    description: str
    request: dict[str, str]


def metadata() -> RecordMetadata:
    return RecordMetadata(
        id="test/record",
        cls="partial_event",
        description="synthetic recorder stream",
        request={"method": "GET", "url": "https://example.test/stream"},
    )


def test_record_iter_keeps_chunk_boundaries_including_empty_chunk() -> None:
    cassette = record_iter(iter([b"a", b"", b"bc"]), **metadata())
    assert [chunk.data for chunk in cassette.chunks] == [b"a", b"", b"bc"]
    assert cassette.body() == b"abc"
    assert cassette.termination.state == "clean_close"
    assert cassette.termination.after_chunk == 2


@pytest.mark.parametrize(
    ("framing", "chunks"),
    [
        ("sse", [b"data: ready\n"]),
        ("ndjson", [b'{"ok":true}']),
        ("raw", [b"\xe2\x82"]),
    ],
)
def test_record_iter_marks_unfinished_framing_or_utf8_as_truncated(
    framing: Literal["sse", "ndjson", "raw"], chunks: list[bytes]
) -> None:
    cassette = record_iter(iter(chunks), framing=framing, **metadata())
    assert cassette.termination.state == "truncated_mid_event"
    assert cassette.termination.after_chunk == len(chunks) - 1
    assert cassette.termination.detail


def test_record_iter_detects_complete_sse_ndjson_and_raw_streams() -> None:
    cases: tuple[tuple[Literal["sse", "ndjson", "raw"], bytes], ...] = (
        ("sse", b"data: ready\n\n"),
        ("ndjson", b'{"ok":true}\n'),
        ("raw", b"bytes"),
    )
    for framing, body in cases:
        result = record_iter(iter([body]), framing=framing, **metadata())
        assert result.termination.state == "clean_close"


def test_source_oserror_becomes_early_close_and_other_errors_propagate() -> None:
    def reset() -> Iterator[bytes]:
        yield b"prefix"
        raise ConnectionResetError("synthetic drop")

    result = record_iter(reset(), **metadata())
    assert result.body() == b"prefix"
    assert result.termination.state == "early_close"
    assert result.termination.error == "ConnectionResetError"
    assert result.termination.after_chunk == 0

    def invalid() -> Iterator[bytes]:
        yield b"prefix"
        raise ValueError("synthetic source bug")

    with pytest.raises(ValueError, match="synthetic source bug"):
        record_iter(invalid(), **metadata())


def test_arecord_iter_matches_sync_record_iter() -> None:
    async def source() -> AsyncIterator[bytes]:
        yield b"data: split\n"
        yield b"\n"

    result = asyncio.run(arecord_iter(source(), framing="sse", **metadata()))
    assert [chunk.data for chunk in result.chunks] == [b"data: split\n", b"\n"]
    assert result.termination.state == "clean_close"
    assert result.body() == b"data: split\n\n"


def test_arecord_iter_preserves_oserror_and_propagates_other_errors() -> None:
    async def reset() -> AsyncIterator[bytes]:
        yield b"prefix"
        raise ConnectionResetError("synthetic async drop")

    result = asyncio.run(arecord_iter(reset(), **metadata()))
    assert result.body() == b"prefix"
    assert result.termination.state == "early_close"
    assert result.termination.error == "ConnectionResetError"

    async def invalid() -> AsyncIterator[bytes]:
        yield b"prefix"
        raise ValueError("synthetic async source bug")

    with pytest.raises(ValueError, match="synthetic async source bug"):
        asyncio.run(arecord_iter(invalid(), **metadata()))


def test_arecord_iter_matches_sync_truncation_decision() -> None:
    async def source() -> AsyncIterator[bytes]:
        yield b"data: unfinished\n"

    sync = record_iter(iter([b"data: unfinished\n"]), framing="sse", **metadata())
    async_result = asyncio.run(arecord_iter(source(), framing="sse", **metadata()))
    assert async_result.termination == sync.termination
    assert async_result.body() == sync.body()
