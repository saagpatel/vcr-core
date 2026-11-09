"""Replay the original bytes and report the recorded terminal outcome."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from .cassette import PartialCassette
    from .termination import Termination


class StreamClosedEarly(ConnectionError):
    def __init__(self, cassette_id: str, delivered: int, error: str) -> None:
        self.cassette_id = cassette_id
        self.delivered = delivered
        self.error = error
        super().__init__(f"{cassette_id}: stream closed after {delivered} bytes ({error})")


class StreamTruncated(EOFError):
    def __init__(self, cassette_id: str, delivered: int, detail: str | None) -> None:
        self.cassette_id = cassette_id
        self.delivered = delivered
        self.detail = detail
        super().__init__(f"{cassette_id}: stream truncated after {delivered} bytes ({detail})")


def replay(c: PartialCassette) -> Iterator[bytes]:
    delivered = 0
    for chunk in c.chunks:
        delivered += len(chunk.data)
        yield chunk.data
    if c.termination.state == "early_close":
        if c.termination.error is None:
            raise ValueError("early_close requires error")
        raise StreamClosedEarly(c.id, delivered, c.termination.error)
    if c.termination.state == "truncated_mid_event":
        raise StreamTruncated(c.id, delivered, c.termination.detail)


async def areplay(c: PartialCassette) -> AsyncIterator[bytes]:
    for chunk in replay(c):
        yield chunk


def replay_bytes(c: PartialCassette) -> tuple[bytes, Termination]:
    chunks: list[bytes] = []
    try:
        chunks.extend(replay(c))
    except (StreamClosedEarly, StreamTruncated):
        pass
    return b"".join(chunks), c.termination
