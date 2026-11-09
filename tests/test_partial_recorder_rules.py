"""Contract amendments: framing-aware truncation inference and explicit overrides."""

from typing import Literal

import pytest

from vcr_core.partial import record_iter

Framing = Literal["sse", "ndjson", "raw"]


def _state(framing: Framing, chunks: list[bytes]) -> str:
    cassette = record_iter(
        iter(chunks),
        framing=framing,
        id="test/rules",
        cls="partial_event",
        description="synthetic recorder rule stream",
        request={"method": "GET", "url": "https://example.test/stream"},
    )
    assert [chunk.data for chunk in cassette.chunks] == chunks
    return cassette.termination.state


@pytest.mark.parametrize(
    "chunks",
    [[b"data: a\n\n"], [b"data: a\r\n\r\n"], [b"data: a\r\r"], [], [b"data: a\r\n", b"\r\n"]],
)
def test_sse_blank_line_terminators_close_cleanly(chunks: list[bytes]) -> None:
    assert _state("sse", chunks) == "clean_close"


@pytest.mark.parametrize("chunks", [[b"data: a\r\n"], [b"data: a\n"], [b"data: \xe2\x82"]])
def test_sse_incomplete_endings_truncate(chunks: list[bytes]) -> None:
    assert _state("sse", chunks) == "truncated_mid_event"


@pytest.mark.parametrize("chunks", [[b'{"x":1}\n'], [b'{"x":1}\r\n'], [], [b'{"a":1}\n\n']])
def test_ndjson_complete_lines_close_cleanly(chunks: list[bytes]) -> None:
    assert _state("ndjson", chunks) == "clean_close"


@pytest.mark.parametrize("chunks", [[b'{"x":\n'], [b'{"x":1}'], [b'{"x":"\xe2\x82\n']])
def test_ndjson_incomplete_values_truncate(chunks: list[bytes]) -> None:
    assert _state("ndjson", chunks) == "truncated_mid_event"


def test_raw_binary_ending_mid_utf8_is_still_clean() -> None:
    assert _state("raw", [b"\x00\xff", b"\xe2"]) == "clean_close"


def test_override_sets_state_and_detail() -> None:
    cassette = record_iter(
        iter([b"abc"]),
        id="test/override",
        cls="partial_event",
        description="override",
        request={"method": "GET", "url": "https://example.test/stream"},
        termination_override="truncated_mid_event",
        detail="cut by design",
    )
    assert cassette.termination.state == "truncated_mid_event"
    assert cassette.termination.detail == "cut by design"


def test_override_cannot_fake_early_close() -> None:
    with pytest.raises(ValueError, match="early_close"):
        record_iter(
            iter([b"abc"]),
            id="test/override",
            cls="early_close",
            description="override",
            request={"method": "GET", "url": "https://example.test/stream"},
            termination_override="early_close",
        )
