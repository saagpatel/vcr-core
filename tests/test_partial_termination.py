"""Termination states round-trip independently and inside a cassette."""

import pytest

from vcr_core.partial import Chunk, PartialCassette, Termination, dump, load


@pytest.mark.parametrize(
    "termination",
    [
        Termination("clean_close", -1),
        Termination("early_close", 0, error="ConnectionResetError"),
        Termination("truncated_mid_event", 1, detail="unfinished frame"),
    ],
)
def test_termination_round_trips_through_dict_and_cassette(
    termination: Termination,
) -> None:
    assert Termination.from_dict(termination.to_dict()) == termination
    chunks = (
        ()
        if termination.after_chunk == -1
        else tuple(Chunk(index, b"x") for index in range(termination.after_chunk + 1))
    )
    cassette = PartialCassette(
        id="test/round-trip",
        cls="partial_event",
        description="synthetic termination case",
        request={"method": "GET", "url": "https://example.test/stream"},
        status=200,
        headers=(),
        chunks=chunks,
        termination=termination,
    )
    assert load(dump(cassette)) == cassette


@pytest.mark.parametrize(
    "data",
    [
        [],
        {"state": "unknown", "after_chunk": -1},
        {"after_chunk": -1},
        {"state": "clean_close", "after_chunk": -1, "unexpected": True},
        {"state": "clean_close", "after_chunk": True},
        {"state": "clean_close", "after_chunk": -1, "error": "Oops"},
        {"state": "early_close", "after_chunk": 0},
        {"state": "early_close", "after_chunk": 0, "error": ""},
        {"state": "truncated_mid_event", "after_chunk": -2},
    ],
)
def test_invalid_termination_is_rejected(data: object) -> None:
    with pytest.raises(ValueError):
        Termination.from_dict(data)


def test_cassette_rejects_after_chunk_mismatch() -> None:
    cassette = PartialCassette(
        id="test/mismatch",
        cls="early_close",
        description="synthetic mismatch",
        request={"method": "GET", "url": "https://example.test/stream"},
        status=200,
        headers=(),
        chunks=(Chunk(0, b"x"),),
        termination=Termination("early_close", -1, error="ConnectionResetError"),
    )
    with pytest.raises(ValueError, match="after_chunk"):
        dump(cassette)
