"""load(dump(c)) == c holds exactly: strict JSON expect values and preserved request order."""

import json

import pytest

from vcr_core.partial import Termination, dump, load, record


def _record(expect: dict[str, object] | None, request: dict[str, str]) -> str:
    cassette = record(
        [b"ab"],
        Termination("clean_close", 0),
        id="test/strict",
        cls="split_codepoint",
        description="strict round trip",
        request=request,
        expect=expect,
    )
    return dump(cassette)


@pytest.mark.parametrize(
    "expect",
    [
        {"nested": {1: "first", "1": "second"}},
        {"tuple": (1, 2)},
        {"bytes": b"x"},
        {"nan": float("nan")},
        {"deep": [{"k": {2: "v"}}]},
    ],
)
def test_non_json_native_expect_is_rejected(expect: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="expect"):
        _record(expect, {"method": "GET", "url": "https://example.test/a"})


def test_json_native_expect_round_trips_exactly() -> None:
    expect: dict[str, object] = {"z": [1, 2.5, None, True, {"a": "é"}], "a": "last"}
    text = _record(expect, {"method": "GET", "url": "https://example.test/a"})
    cassette = load(text)
    assert cassette.expect == expect
    assert list(cassette.expect or {}) == ["z", "a"]
    assert dump(cassette) == text


def test_request_key_order_is_preserved() -> None:
    text = _record(None, {"url": "https://example.test/a", "method": "GET"})
    assert list(json.loads(text)["request"]) == ["url", "method"]
    cassette = load(text)
    assert list(cassette.request) == ["url", "method"]
    assert dump(cassette) == text
