"""Replay preserves recorded byte boundaries and reports incomplete endings."""

import asyncio

import pytest

from vcr_core.partial import (
    Chunk,
    PartialCassette,
    StreamClosedEarly,
    StreamTruncated,
    Termination,
    areplay,
    replay,
    replay_bytes,
)


def make_cassette(chunks: tuple[bytes, ...], termination: Termination) -> PartialCassette:
    return PartialCassette(
        id="test/replay",
        cls="early_close" if termination.state == "early_close" else "partial_event",
        description="synthetic replay",
        request={"method": "GET", "url": "https://example.test/stream"},
        status=200,
        headers=(),
        chunks=tuple(Chunk(i, chunk) for i, chunk in enumerate(chunks)),
        termination=termination,
    )


@pytest.mark.parametrize(
    ("chunks", "termination"),
    [
        ((b"complete", b""), Termination("clean_close", 1)),
        ((b"useful",), Termination("early_close", 0, error="ConnectionResetError")),
        ((b"unfinished",), Termination("truncated_mid_event", 0, detail="partial frame")),
        ((b"\xe2", b"\x82\xac"), Termination("clean_close", 1)),
        (
            (b"\xf0", b"\x9f", b"\x8c", b"\x8a"),
            Termination("clean_close", 3),
        ),
    ],
)
def test_replay_preserves_bytes_and_chunk_boundaries(
    chunks: tuple[bytes, ...], termination: Termination
) -> None:
    cassette = make_cassette(chunks, termination)
    if termination.state == "clean_close":
        assert list(replay(cassette)) == list(chunks)
        assert replay_bytes(cassette) == (b"".join(chunks), termination)
        return

    iterator = replay(cassette)
    delivered: list[bytes] = []
    for chunk in chunks:
        delivered.append(next(iterator))
        assert delivered[-1] == chunk
    expected_error = StreamClosedEarly if termination.state == "early_close" else StreamTruncated
    with pytest.raises(expected_error):
        next(iterator)


def test_early_close_exception_has_recorded_attributes_after_chunks() -> None:
    cassette = make_cassette(
        (b"one", b"two"), Termination("early_close", 1, "ConnectionResetError")
    )
    iterator = replay(cassette)
    assert next(iterator) == b"one"
    assert next(iterator) == b"two"
    with pytest.raises(StreamClosedEarly) as caught:
        next(iterator)
    assert isinstance(caught.value, ConnectionError)
    assert (caught.value.cassette_id, caught.value.delivered, caught.value.error) == (
        "test/replay",
        6,
        "ConnectionResetError",
    )
    assert replay_bytes(cassette) == (b"onetwo", cassette.termination)


def test_truncated_exception_has_recorded_attributes_after_chunks() -> None:
    cassette = make_cassette((b"part",), Termination("truncated_mid_event", 0, detail="cut"))
    iterator = replay(cassette)
    assert next(iterator) == b"part"
    with pytest.raises(StreamTruncated) as caught:
        next(iterator)
    assert isinstance(caught.value, EOFError)
    assert (caught.value.cassette_id, caught.value.delivered, caught.value.detail) == (
        "test/replay",
        4,
        "cut",
    )
    assert replay_bytes(cassette) == (b"part", cassette.termination)


def test_areplay_has_sync_replay_parity() -> None:
    async def collect(cassette: PartialCassette) -> tuple[list[bytes], type[BaseException] | None]:
        chunks: list[bytes] = []
        try:
            async for chunk in areplay(cassette):
                chunks.append(chunk)
        except (StreamClosedEarly, StreamTruncated) as error:
            return chunks, type(error)
        return chunks, None

    cases = (
        ((b"\xf0", b"\x9f", b"\x8c", b"\x8a"), Termination("clean_close", 3)),
        ((b"one", b"two"), Termination("early_close", 1, "ConnectionResetError")),
        ((b"partial",), Termination("truncated_mid_event", 0, detail="cut")),
    )
    for chunks, termination in cases:
        cassette = make_cassette(chunks, termination)
        expected_error = {
            "clean_close": None,
            "early_close": StreamClosedEarly,
            "truncated_mid_event": StreamTruncated,
        }[termination.state]
        async_chunks, async_error = asyncio.run(collect(cassette))
        sync_chunks: list[bytes] = []
        sync_error: type[BaseException] | None = None
        try:
            sync_chunks.extend(replay(cassette))
        except (StreamClosedEarly, StreamTruncated) as error:
            sync_error = type(error)
        assert async_chunks == sync_chunks == list(chunks)
        assert async_error is sync_error is expected_error
