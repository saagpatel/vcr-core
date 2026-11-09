"""Partial cassette validation, canonical serialization and schema agreement."""

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import jsonschema
import pytest

from vcr_core.partial import Chunk, PartialCassette, Termination, dump, load, validate_partial


def cassette() -> PartialCassette:
    return PartialCassette(
        id="split-codepoints/synthetic",
        cls="split_codepoint",
        description="synthetic split bytes",
        request={"method": "GET", "url": "https://example.test/stream"},
        status=200,
        headers=(("x-part", "one"), ("x-part", "two")),
        chunks=(Chunk(0, b""), Chunk(1, b"\xe2\x82"), Chunk(2, b"\xac")),
        termination=Termination("clean_close", 2),
    )


def mutate_bad_b64(doc: dict[str, object]) -> None:
    chunks = cast("list[object]", doc["chunks"])
    cast("dict[str, object]", chunks[0]).update({"b64": "***"})


def mutate_index_gap(doc: dict[str, object]) -> None:
    chunks = cast("list[object]", doc["chunks"])
    cast("dict[str, object]", chunks[1]).update({"index": 9})


def mutate_bad_header(doc: dict[str, object]) -> None:
    response = cast("dict[str, object]", doc["response"])
    response.update({"headers": [["name"]]})


def test_valid_cassette_passes_python_and_jsonschema_validation() -> None:
    document = cassette().to_dict()
    validate_partial(document)
    schema_path = (
        Path(__file__).parents[1] / "vcr_core/partial/schema/partial-stream-v1.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(document, schema)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda doc: doc.update({"format": "wrong/v1"}), "format"),
        (lambda doc: doc.pop("id"), "id"),
        (lambda doc: doc.update({"surprise": True}), "surprise"),
        (mutate_bad_b64, "base64"),
        (mutate_index_gap, "index"),
        (lambda doc: doc.update({"body_sha256": "0" * 64}), "sha256"),
        (lambda doc: doc.update({"class": "unknown"}), "class"),
        (mutate_bad_header, "header"),
    ],
)
def test_invalid_cassettes_are_rejected(
    mutate: Callable[[dict[str, object]], None], message: str
) -> None:
    document = copy.deepcopy(cassette().to_dict())
    mutate(document)
    with pytest.raises(ValueError, match=message):
        validate_partial(document)


def test_dump_and_load_are_canonical_and_preserve_header_and_chunk_order() -> None:
    source = cassette()
    text = dump(source)
    assert text.endswith("\n")
    assert dump(load(text)) == text
    loaded = load(text)
    assert loaded.headers == (("x-part", "one"), ("x-part", "two"))
    assert [chunk.data for chunk in loaded.chunks] == [b"", b"\xe2\x82", b"\xac"]
