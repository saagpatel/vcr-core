"""UTF-8 boundaries remain byte-faithful and incrementally decodable."""

import codecs
from typing import cast

from vcr_core.partial import PartialCassette, iter_fixtures, replay


def _fixtures() -> list[PartialCassette]:
    return [c for c in iter_fixtures() if c.cls == "split_codepoint"]


def test_split_codepoint_fixtures_decode_incrementally() -> None:
    assert len(_fixtures()) == 10
    for cassette in _fixtures():
        chunks = list(replay(cassette))
        assert b"".join(chunks) == cassette.body()
        assert any(_invalid_utf8(chunk) for chunk in chunks)
        decoder = codecs.getincrementaldecoder("utf-8")()
        text = "".join(decoder.decode(chunk) for chunk in chunks) + decoder.decode(b"", final=True)
        assert "\ufffd" not in text
        expect = cast("dict[str, object]", cassette.expect)
        assert text == expect["decoded_text"]
        raw = cassette.body()
        for point in cast("list[int]", expect["split_points"]):
            assert 0 < point < len(raw)
            assert raw[point] & 0xC0 == 0x80


def _invalid_utf8(chunk: bytes) -> bool:
    try:
        chunk.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False
