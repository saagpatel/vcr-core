"""Opt-in recording and replay of partial HTTP-style byte streams."""

from collections.abc import Iterator
from pathlib import Path

from .cassette import FORMAT_TAG, Chunk, PartialCassette, dump, load, validate_partial
from .recorder import arecord_iter, record, record_iter
from .replay import StreamClosedEarly, StreamTruncated, areplay, replay, replay_bytes
from .termination import Termination, TerminationState

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def iter_fixtures() -> Iterator[PartialCassette]:
    for path in sorted(FIXTURES_DIR.glob("**/*.pcas.json")):
        yield load(path)


__all__ = [
    "TerminationState",
    "Termination",
    "Chunk",
    "PartialCassette",
    "load",
    "dump",
    "validate_partial",
    "record",
    "record_iter",
    "arecord_iter",
    "replay",
    "areplay",
    "replay_bytes",
    "StreamClosedEarly",
    "StreamTruncated",
    "FORMAT_TAG",
    "FIXTURES_DIR",
    "iter_fixtures",
]
