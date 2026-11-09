"""Truncated fixture replay preserves incomplete framed tails."""

import base64
from typing import cast

import pytest

from vcr_core.partial import StreamTruncated, iter_fixtures, replay


def test_partial_events_replay_exact_incomplete_units() -> None:
    fixtures = [c for c in iter_fixtures() if c.cls == "partial_event"]
    assert len(fixtures) == 10
    for cassette in fixtures:
        delivered = []
        with pytest.raises(StreamTruncated) as raised:
            for chunk in replay(cassette):
                delivered.append(chunk)
        body = b"".join(delivered)
        expect = cast("dict[str, object]", cassette.expect)
        tail = base64.b64decode(cast("str", expect["tail_b64"]))
        assert raised.value.delivered == cast("int", expect["truncated_at_byte"]) == len(body)
        assert body == cassette.body() and body.endswith(tail)
        if cassette.id.endswith("chat-after-three"):
            assert body.count(b"\n\n") == cast("int", expect["complete_events"]) == 3
        elif "ndjson" in cassette.id:
            assert body.count(b"\n") == cast("int", expect["complete_events"])
        else:
            assert body.count(b"\n\n") == cast("int", expect["complete_events"])
