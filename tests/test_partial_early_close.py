"""Early-close fixtures surface the recorded useful prefix and error."""

import base64
from typing import cast

import pytest

from vcr_core.partial import StreamClosedEarly, iter_fixtures, replay


def test_early_close_fixtures_raise_after_the_recorded_prefix() -> None:
    fixtures = [c for c in iter_fixtures() if c.cls == "early_close"]
    assert len(fixtures) == 10
    for cassette in fixtures:
        chunks = []
        with pytest.raises(StreamClosedEarly) as raised:
            for chunk in replay(cassette):
                chunks.append(chunk)
        expect = cast("dict[str, object]", cassette.expect)
        assert b"".join(chunks) == base64.b64decode(cast("str", expect["useful_prefix_b64"]))
        assert raised.value.error == cassette.termination.error
        assert raised.value.delivered == len(cassette.body())
        if cassette.id.endswith("ndjson-log"):
            assert cassette.body().count(b"\n") == cast("int", expect["complete_events"])
        elif expect["complete_events"] is not None:
            assert cassette.body().count(b"\n\n") == cast("int", expect["complete_events"])
