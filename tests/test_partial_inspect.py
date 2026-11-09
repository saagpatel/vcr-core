"""HTML inspection pages and the partial-stream inspect/serve CLI."""

import hashlib
import html
import re
import selectors
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import pytest

from vcr_core.partial import Termination, dump, iter_fixtures, record
from vcr_core.partial.cassette import PartialCassette
from vcr_core.partial.inspect import render_cassette, render_index, write_site

Kind = Literal["split_codepoint", "partial_event", "early_close"]
_EMOJI = "😀"
_ROOT = Path(__file__).parents[1]


def _make(
    chunks: Sequence[bytes],
    termination: Termination,
    cassette_id: str,
    kind: Kind,
    description: str,
    headers: Sequence[tuple[str, str]] = (("content-type", "text/plain"),),
) -> PartialCassette:
    return record(
        chunks,
        termination,
        id=cassette_id,
        cls=kind,
        description=description,
        request={"method": "GET", "url": "https://example.test/stream"},
        headers=headers,
    )


def _synthetic() -> list[PartialCassette]:
    emoji = _EMOJI.encode()
    return [
        _make(
            [b"a\nb\t\r\x00"],
            Termination("clean_close", 0),
            "synthetic/clean-close",
            "split_codepoint",
            "clean close with visible controls",
            headers=(("x-a", "1"), ("x-b", "2"), ("x-a", "3")),
        ),
        _make(
            [b"partial"],
            Termination("early_close", 0, error="ConnectionResetError"),
            "synthetic/early-close",
            "early_close",
            "transport reset after one chunk",
        ),
        _make(
            [b"\xf0\x9f\x98"],
            Termination("truncated_mid_event", 0, detail="cut after 3 emoji bytes"),
            "synthetic/truncated",
            "partial_event",
            "truncated inside a 4-byte codepoint",
        ),
        _make(
            [emoji[:2], b"", emoji[2:]],
            Termination("clean_close", 2),
            "synthetic/split-emoji",
            "split_codepoint",
            "four-byte emoji split around an empty chunk",
        ),
        _make(
            [b""],
            Termination("clean_close", 0),
            "synthetic/empty-chunk",
            "partial_event",
            "<script>alert(1)</script>",
            headers=(("x-note", "<script>"),),
        ),
        _make(
            [b"A\xffB", b"\xc3", b"("],
            Termination("truncated_mid_event", 2, detail="invalid bytes"),
            "synthetic/invalid-bytes",
            "partial_event",
            "invalid UTF-8 rendered as hex badges",
        ),
        _make(
            [],
            Termination("early_close", -1, error="BrokenPipeError"),
            "synthetic/no-chunks",
            "early_close",
            "reset before any chunk",
        ),
    ]


def _pages() -> list[PartialCassette]:
    return [*iter_fixtures(), *_synthetic()]


def _chunk_rows(page: str) -> list[tuple[int, str]]:
    marks = list(re.finditer(r'data-chunk-index="(\d+)"', page))
    rows: list[tuple[int, str]] = []
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(page)
        rows.append((int(mark.group(1)), page[mark.start() : end]))
    return rows


@pytest.mark.parametrize("cassette", _pages(), ids=lambda cassette: cassette.id)
def test_cassette_page_lists_chunks_termination_and_escapes(cassette: PartialCassette) -> None:
    page = render_cassette(cassette)
    rows = _chunk_rows(page)
    assert [index for index, _row in rows] == list(range(len(cassette.chunks)))
    assert re.findall(r'data-termination="([^"]*)"', page) == [cassette.termination.state]
    for chunk in cassette.chunks:
        assert chunk.data.hex() in page
    assert "<script>" not in page
    assert "<script" not in page.lower()
    assert html.escape(cassette.id) in page
    assert html.escape(cassette.description) in page
    assert html.escape(cassette.request["method"]) in page
    assert html.escape(cassette.request["url"]) in page
    assert cassette.termination.state in page
    assert "after_chunk" in page
    assert "error" in page
    assert "detail" in page
    assert "total bytes" in page
    assert "chunk count" in page
    assert "body sha256" in page
    assert hashlib.sha256(cassette.body()).hexdigest() in page
    assert "prefers-color-scheme" in page
    if cassette.termination.state == "clean_close":
        assert "■ clean close" in page
    elif cassette.termination.state == "early_close":
        assert cassette.termination.error is not None
        assert f"✂ connection reset: {cassette.termination.error}" in page
    else:
        assert "⋯ truncated mid-event:" in page
        if cassette.termination.detail:
            assert html.escape(cassette.termination.detail) in page


def test_split_emoji_is_shown_once_in_the_completing_chunk() -> None:
    cassette = next(item for item in _synthetic() if item.id == "synthetic/split-emoji")
    page = render_cassette(cassette)
    rows = dict(_chunk_rows(page))
    assert _EMOJI not in rows[0]
    assert _EMOJI not in rows[1]
    assert rows[2].count(_EMOJI) == 1
    assert page.count(_EMOJI) == 1
    assert "↪ carries 2 bytes" in rows[0]
    assert "(empty chunk)" in rows[1]
    assert "completes split codepoint" in rows[2]
    assert "completes split codepoint" not in rows[0]


def test_empty_chunk_controls_headers_and_escaping() -> None:
    clean = next(item for item in _synthetic() if item.id == "synthetic/clean-close")
    page = render_cassette(clean)
    row = dict(_chunk_rows(page))[0]
    assert "␊" in row
    assert "␉" in row
    assert "␍" in row
    assert "␀" in row
    body = page.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    assert body.index(">1<") < body.index(">2<") < body.index(">3<")

    escaped = next(item for item in _synthetic() if item.id == "synthetic/empty-chunk")
    escaped_page = render_cassette(escaped)
    assert "(empty chunk)" in dict(_chunk_rows(escaped_page))[0]
    assert "&lt;script&gt;" in escaped_page
    assert "<script>" not in escaped_page


def test_invalid_bytes_are_hex_badges_and_truncated_tail_stays_undecoded() -> None:
    invalid = next(item for item in _synthetic() if item.id == "synthetic/invalid-bytes")
    page = render_cassette(invalid)
    rows = dict(_chunk_rows(page))
    assert "\ufffd" not in page
    assert '<span class="hex-badge">ff</span>' in rows[0]
    assert '<span class="run">A</span>' in rows[0]
    assert '<span class="run">B</span>' in rows[0]
    assert "↪ carries 1 byte" in rows[1]
    assert '<span class="hex-badge">c3</span>' in rows[2]
    assert "completes split codepoint" not in page
    assert "(" in rows[2]

    truncated = next(item for item in _synthetic() if item.id == "synthetic/truncated")
    truncated_page = render_cassette(truncated)
    assert _EMOJI not in truncated_page
    assert 'data-tail-hex="f09f98"' in truncated_page
    assert '<span class="hex-badge">f0</span>' in truncated_page
    assert "⋯ truncated mid-event: cut after 3 emoji bytes" in truncated_page


def test_arbitrary_bytes_render_without_raising() -> None:
    blobs = [bytes(range(256)), b"\xed\xa0\x80", b"\xf5\x80\x80\x80", b"\xef\xbf\xbd"]
    cassette = _make(
        blobs,
        Termination("truncated_mid_event", len(blobs) - 1, detail="every byte"),
        "synthetic/all-bytes",
        "partial_event",
        "rendering must accept arbitrary bytes",
    )
    page = render_cassette(cassette)
    assert [index for index, _row in _chunk_rows(page)] == list(range(len(blobs)))
    assert page.count("\ufffd") == 1
    for blob in blobs:
        assert blob.hex() in page


def test_index_links_every_written_page(tmp_path: Path) -> None:
    cassettes = _synthetic()[:2]
    duplicated = [
        *cassettes,
        _make(
            [b"x"],
            Termination("clean_close", 0),
            cassettes[0].id,
            "split_codepoint",
            "<script>",
        ),
    ]
    index_path = write_site(duplicated, tmp_path)
    index = index_path.read_text(encoding="utf-8")
    hrefs = re.findall(r'href="([^"]+)"', index)
    pages = [
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*.html")
        if path.name != "index.html"
    ]
    assert set(hrefs) == set(pages)
    assert len(hrefs) == len(duplicated)
    assert "<script>" not in index
    rendered = render_index([("nested/one.html", duplicated[0])])
    assert 'href="nested/one.html"' in rendered


def test_inspect_bundled_and_paths(tmp_path: Path) -> None:
    bundled_out = tmp_path / "bundled"
    bundled = _run(
        "inspect",
        "--bundled",
        "--out",
        str(bundled_out),
    )
    assert bundled.returncode == 0, bundled.stderr
    assert bundled.stdout.strip() == str(bundled_out / "index.html")
    _assert_site(bundled_out)

    source = tmp_path / "inputs"
    nested = source / "nested"
    nested.mkdir(parents=True)
    first, second = _synthetic()[0], _synthetic()[3]
    (source / "one.pcas.json").write_text(dump(first), encoding="utf-8")
    (nested / "two.pcas.json").write_text(dump(second), encoding="utf-8")
    file_out = tmp_path / "from-file"
    inspected = _run("inspect", str(source / "one.pcas.json"), "--out", str(file_out))
    assert inspected.returncode == 0, inspected.stderr
    assert inspected.stdout.strip() == str(file_out / "index.html")
    _assert_site(file_out)
    assert first.id in (file_out / "index.html").read_text(encoding="utf-8")

    dir_out = tmp_path / "from-dir"
    inspected_dir = _run("inspect", str(source), "--out", str(dir_out))
    assert inspected_dir.returncode == 0, inspected_dir.stderr
    _assert_site(dir_out)
    index = (dir_out / "index.html").read_text(encoding="utf-8")
    assert first.id in index
    assert second.id in index


def test_count_and_validate_remain_available(tmp_path: Path) -> None:
    counted = _run("count")
    assert counted.returncode == 0, counted.stderr
    assert "total=" in counted.stdout
    path = tmp_path / "ok.pcas.json"
    path.write_text(dump(_synthetic()[0]), encoding="utf-8")
    validated = _run("validate", str(path))
    assert validated.returncode == 0, validated.stderr
    rejected = _run("inspect")
    assert rejected.returncode == 1


def test_serve_smoke_on_an_ephemeral_port(tmp_path: Path) -> None:
    path = tmp_path / "one.pcas.json"
    cassette = _synthetic()[3]
    path.write_text(dump(cassette), encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "vcr_core.partial", "serve", "--port", "0", str(path)],
        cwd=_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        ready = selector.select(timeout=5)
        if not ready:
            process.terminate()
            raise AssertionError(process.stderr.read())
        line = process.stdout.readline().strip()
        assert line.startswith("http://127.0.0.1:")
        assert line.endswith("/index.html")
        index_html = _get(line)
        assert cassette.id in index_html
        href = re.search(r'href="([^"]+\.html)"', index_html)
        assert href is not None
        page = _get(line.removesuffix("index.html") + href.group(1))
        assert 'data-chunk-index="0"' in page
        assert 'data-termination="clean_close"' in page
        assert _EMOJI in page
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        selector.close()


def _assert_site(out: Path) -> None:
    index = (out / "index.html").read_text(encoding="utf-8")
    hrefs = re.findall(r'href="([^"]+)"', index)
    pages = [
        path.relative_to(out).as_posix()
        for path in out.rglob("*.html")
        if path.name != "index.html"
    ]
    assert set(hrefs) == set(pages)
    for href in hrefs:
        target = out / href
        assert target.is_file()
        assert "<script>" not in target.read_text(encoding="utf-8")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "vcr_core.partial", *args],
        cwd=_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _get(url: str) -> str:
    deadline = time.monotonic() + 2
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                assert response.status == 200
                body = response.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
            time.sleep(0.05)
            continue
        assert isinstance(body, bytes)
        return body.decode("utf-8")
    raise AssertionError(f"GET {url} failed: {last_error}")
