"""Build the deterministic synthetic Partial Stream Studio fixture set."""

from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Literal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vcr_core.partial import Termination, dump, record, record_iter  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Iterator

    from vcr_core.partial import PartialCassette, TerminationState

OUT = ROOT / "vcr_core" / "partial" / "fixtures"
REQUEST = {"method": "GET", "url": "https://example.test/stream"}


def splits(text: str, positions: list[int]) -> tuple[list[bytes], list[int]]:
    raw = text.encode("utf-8")
    points = sorted(set(positions))
    return [raw[a:b] for a, b in zip([0, *points], [*points, len(raw)])], points


def split_fixtures() -> list[tuple[str, PartialCassette]]:
    cases = [
        ("e-acute-2-1", "café", [4, 5]),
        ("sharp-s-1-1", "ß", [1]),
        ("euro-1-2", "€", [1]),
        ("cjk-2-1", "中", [2]),
        ("check-1-1-1", "✓", [1, 2]),
        ("smile-four-chunks", "🙂", [1, 2, 3]),
        ("music-empty-middle", "𝄞", [1, 2]),
        ("combining-sequence", "e\u0301", [2]),
        ("zwj-sequence", "👩\u200d💻", [5, 6, 9]),
        ("sse-and-ndjson", 'data: 中\n{"text":"é"}\n', [8, 9, 20]),
    ]
    result = []
    for number, (slug, text, positions) in enumerate(cases, 1):
        chunks, _ = splits(text, positions)
        if slug == "music-empty-middle":
            chunks = [chunks[0], b"", chunks[1], chunks[2]]
        if slug == "sse-and-ndjson":
            # Keep an actual codepoint boundary split inside both framed examples.
            chunks = [b"data: \xe4", b'\xb8\xad\n{"text":"\xc3', b'\xa9"}\n']
        offsets: list[int] = []
        offset = 0
        for chunk in chunks[:-1]:
            offset += len(chunk)
            if offset and offset < len(text.encode()):
                if (text.encode()[offset] & 0xC0) == 0x80:
                    if offset not in offsets:
                        offsets.append(offset)
        c = record(
            chunks,
            _term("clean_close", len(chunks) - 1),
            id=f"split-codepoints/{number:02d}-{slug}",
            cls="split_codepoint",
            description=f"Synthetic UTF-8 split: {slug}.",
            request=REQUEST,
            expect={"decoded_text": text, "split_points": offsets},
        )
        result.append((f"split-codepoints/{number:02d}-{slug}.pcas.json", c))
    return result


def _term(
    state: TerminationState, after: int, *, error: str | None = None, detail: str | None = None
) -> Termination:
    return Termination(state, after, error=error, detail=detail)


def partial_fixtures() -> list[tuple[str, PartialCassette]]:
    cases: list[tuple[str, bytes, Literal["sse", "ndjson"], int, str]] = [
        ("sse-mid-string", b'data: {"text":"hel', "sse", 0, 'data: {"text":...'),
        ("sse-mid-key", b'data: {"tok', "sse", 0, "SSE JSON key is incomplete"),
        ("sse-after-data", b"data:", "sse", 0, "SSE payload is absent"),
        ("sse-between-newlines", b"data: hi\n", "sse", 0, "event delimiter is incomplete"),
        (
            "sse-multiline-line-two",
            b"data: first\ndata: sec",
            "sse",
            0,
            "second data line is incomplete",
        ),
        ("ndjson-mid-number", b'{"n":12', "ndjson", 0, "JSON number is incomplete"),
        ("ndjson-mid-escape", b'{"s":"\\u00', "ndjson", 0, "JSON escape is incomplete"),
        ("ndjson-mid-multibyte", b'{"s":"\xe4', "ndjson", 0, "UTF-8 codepoint is incomplete"),
        (
            "chat-after-three",
            (
                b'data: {"token":"a"}\n\ndata: {"token":"b"}\n\n'
                b'data: {"token":"c"}\n\ndata: {"token":"d'
            ),
            "sse",
            3,
            "fourth token event is incomplete",
        ),
        ("done-sentinel", b"data: [DO", "sse", 0, "DONE sentinel is incomplete"),
    ]
    result = []
    for number, (slug, body, framing, complete, detail) in enumerate(cases, 1):
        boundary = body.rfind(b"\n\n") + 2 if framing == "sse" else body.rfind(b"\n") + 1
        tail = body[boundary:] if complete or (framing == "sse" and b"\n\n" in body) else body
        chunks = [body]
        c = record_iter(
            chunks,
            framing=framing,
            id=f"partial-events/{number:02d}-{slug}",
            cls="partial_event",
            description=f"Synthetic truncated stream: {slug}.",
            request=REQUEST,
            expect={
                "complete_events": complete,
                "truncated_at_byte": len(body),
                "tail_b64": base64.b64encode(tail).decode("ascii"),
            },
            termination_override="truncated_mid_event",
            detail=detail,
        )
        result.append((f"partial-events/{number:02d}-{slug}.pcas.json", c))
    return result


def early_fixtures() -> list[tuple[str, PartialCassette]]:
    cases: list[tuple[str, list[bytes], Literal["sse", "ndjson", "raw"], int | None, str, str]] = [
        (
            "two-sse-events",
            [b"data: one\n\ndata: two\n\n"],
            "sse",
            2,
            "ConnectionResetError",
            "text/event-stream",
        ),
        ("headers-only", [], "raw", None, "TimeoutError", "application/octet-stream"),
        ("json-array-element", [b"[1,", b"2,"], "raw", None, "BrokenPipeError", "application/json"),
        (
            "event-boundary",
            [b"data: ready\n\n"],
            "sse",
            1,
            "ConnectionAbortedError",
            "text/event-stream",
        ),
        ("keepalive", [b": ping\n"], "raw", 0, "ConnectionResetError", "text/event-stream"),
        ("large-chunk", [b"x" * 65536], "raw", None, "TimeoutError", "text/plain"),
        (
            "tiny-chunks",
            [bytes([i]) for i in range(65)],
            "raw",
            None,
            "BrokenPipeError",
            "application/octet-stream",
        ),
        (
            "plain-text-cut",
            [b"Synthetic download is par"],
            "raw",
            None,
            "ConnectionResetError",
            "text/plain",
        ),
        (
            "ndjson-log",
            [b'{"level":"info"}\n', b'{"level":"warn"}\n'],
            "ndjson",
            2,
            "ConnectionAbortedError",
            "application/x-ndjson",
        ),
        (
            "split-codepoint-completes",
            [b"ok \xe2", b"\x82", b"\xac"],
            "raw",
            None,
            "TimeoutError",
            "text/plain",
        ),
    ]
    result = []
    for number, (slug, chunks, framing, count, error, content_type) in enumerate(cases, 1):
        source = _raising_source(chunks, error)
        cassette = record_iter(
            source,
            framing=framing,
            id=f"early-close/{number:02d}-{slug}",
            cls="early_close",
            description=f"Synthetic early close: {slug}.",
            request=REQUEST,
            headers=(("content-type", content_type),),
            expect={
                "useful_prefix_b64": base64.b64encode(b"".join(chunks)).decode("ascii"),
                "complete_events": count,
            },
        )
        result.append((f"early-close/{number:02d}-{slug}.pcas.json", cassette))
    return result


def _raising_source(chunks: list[bytes], error: str) -> Iterator[bytes]:
    yield from chunks
    raise {
        "ConnectionResetError": ConnectionResetError,
        "BrokenPipeError": BrokenPipeError,
        "ConnectionAbortedError": ConnectionAbortedError,
        "TimeoutError": TimeoutError,
    }[error]("synthetic drop")


def build() -> dict[Path, str]:
    items = split_fixtures() + partial_fixtures() + early_fixtures()
    return {OUT / path: dump(cassette) for path, cassette in items}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="fail if any generated fixture is missing or different"
    )
    args = parser.parse_args()
    generated = build()
    if args.check:
        bad = [
            path
            for path, text in generated.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != text
        ]
        extra = sorted(OUT.glob("**/*.pcas.json"))
        expected = set(generated)
        bad.extend(path for path in extra if path not in expected)
        if bad:
            print(
                "fixture mismatch: " + ", ".join(str(path.relative_to(ROOT)) for path in bad),
                file=sys.stderr,
            )
            return 1
        return 0
    for path, text in generated.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
