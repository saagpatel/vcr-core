"""Sync and async replay preserve chunk boundaries and content."""

import asyncio
import hashlib

from vcr_core.partial import (
    PartialCassette,
    StreamClosedEarly,
    StreamTruncated,
    areplay,
    iter_fixtures,
    replay,
    replay_bytes,
)


def test_all_fixtures_replay_chunks_and_termination() -> None:
    fixtures = list(iter_fixtures())
    assert len(fixtures) == 30
    for cassette in fixtures:
        expected = [chunk.data for chunk in cassette.chunks]
        assert _collect_sync(cassette) == expected
        assert asyncio.run(_collect(cassette)) == expected
        assert hashlib.sha256(b"".join(expected)).hexdigest() == cassette.to_dict()["body_sha256"]
        assert replay_bytes(cassette) == (b"".join(expected), cassette.termination)


async def _collect(cassette: PartialCassette) -> list[bytes]:
    chunks: list[bytes] = []
    try:
        async for chunk in areplay(cassette):
            chunks.append(chunk)
    except (StreamClosedEarly, StreamTruncated):
        pass
    return chunks


def _collect_sync(cassette: PartialCassette) -> list[bytes]:
    chunks: list[bytes] = []
    try:
        chunks.extend(replay(cassette))
    except (StreamClosedEarly, StreamTruncated):
        pass
    return chunks
