"""Self-contained HTML inspection for partial-stream cassettes."""

import hashlib
import html
import http.server
import re
import socket
import socketserver
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .cassette import Chunk, PartialCassette
from .termination import Termination

_CSS = """
:root {
  color-scheme: light dark;
  --bg: #f4f1ea;
  --fg: #1f1a17;
  --muted: #5c534c;
  --card: #fffdf8;
  --line: #e4ddd2;
  --accent: #9a3412;
  --mono: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
  --sans: "Iowan Old Style", Palatino, "Palatino Linotype", Georgia, serif;
  --ui: "Avenir Next", "Segoe UI", sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #141311;
    --fg: #f5f1ea;
    --muted: #b7ada3;
    --card: #221f1c;
    --line: #3a342e;
    --accent: #fdba74;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font: 16px/1.5 var(--ui);
}
main { max-width: 70rem; margin: 0 auto; padding: 1.25rem 1rem 3rem; }
h1 { font-family: var(--sans); font-size: 1.8rem; line-height: 1.2; margin: 0.2rem 0; }
h1, .desc, .url, .detail, .terminal-label { overflow-wrap: anywhere; }
a { color: var(--accent); }
a:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
.eyebrow, .meta, .chunk-meta, .summary, .pill { color: var(--muted); }
.card, .chunk, .terminal, .term {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 14px;
}
.card, .term, .terminal { padding: 0.9rem 1rem; margin: 0.8rem 0; }
.term { border-left-width: 8px; }
.term-clean_close { background: #e5f6ec; color: #064e3b; border-color: #0f6b3c; }
.term-early_close { background: #fde8ee; color: #881337; border-color: #be123c; }
.term-truncated_mid_event { background: #ffedd5; color: #9a3412; border-color: #c2410c; }
@media (prefers-color-scheme: dark) {
  .term-clean_close { background: #123524; color: #d1fae5; border-color: #34d399; }
  .term-early_close { background: #4c0519; color: #ffe4e6; border-color: #fb7185; }
  .term-truncated_mid_event { background: #431407; color: #ffedd5; border-color: #fb923c; }
}
.term dl {
  display: grid;
  grid-template-columns: 8rem 1fr;
  gap: 0.2rem 0.75rem;
  margin: 0.4rem 0 0;
}
.term dt { font-weight: 650; }
.term dd { margin: 0; font-family: var(--mono); }
.state-label, .method, code, .hex, .text, .badge, .hex-badge { font-family: var(--mono); }
.method {
  font-weight: 700;
  letter-spacing: 0.04em;
}
table { width: 100%; border-collapse: collapse; }
th, td {
  text-align: left;
  vertical-align: top;
  padding: 0.35rem 0.5rem;
  border-bottom: 1px solid var(--line);
}
th { font-size: 0.78rem; letter-spacing: 0.04em; text-transform: uppercase; color: var(--muted); }
.chunk {
  display: grid;
  grid-template-columns: 4.5rem minmax(0, 1fr);
  gap: 0.5rem 0.8rem;
  padding: 0.75rem;
  margin: 0.55rem 0;
}
.chunk-index { font: 700 1.1rem/1 var(--mono); }
.views { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 0.6rem; }
pre.hex, .text {
  margin: 0;
  padding: 0.55rem 0.65rem;
  border-radius: 10px;
  background: color-mix(in srgb, var(--line) 55%, transparent);
  max-width: 100%;
}
pre.hex { overflow-x: auto; white-space: pre; }
.text { white-space: pre-wrap; overflow-wrap: anywhere; min-height: 2.4rem; }
.badge, .pill {
  display: inline-block;
  border-radius: 999px;
  padding: 0.05rem 0.5rem;
  background: color-mix(in srgb, var(--line) 80%, transparent);
  font-size: 0.78rem;
}
.badge.complete { background: #dbeafe; color: #1e3a8a; }
.badge.carry { background: #fef3c7; color: #92400e; }
.pill.term-clean_close { background: #e5f6ec; color: #064e3b; }
.pill.term-early_close { background: #fde8ee; color: #881337; }
.pill.term-truncated_mid_event { background: #ffedd5; color: #9a3412; }
@media (prefers-color-scheme: dark) {
  .badge.complete { background: #1e3a8a; color: #dbeafe; }
  .badge.carry { background: #78350f; color: #fef3c7; }
  .pill.term-clean_close { background: #123524; color: #d1fae5; }
  .pill.term-early_close { background: #4c0519; color: #ffe4e6; }
  .pill.term-truncated_mid_event { background: #431407; color: #ffedd5; }
}
.hex-badge {
  display: inline-block;
  margin: 0 0.08rem;
  padding: 0 0.28rem;
  border-radius: 4px;
  background: #7c2d12;
  color: #fff7ed;
  font-size: 0.85em;
}
@media (prefers-color-scheme: dark) {
  .hex-badge { background: #fdba74; color: #431407; }
}
.empty { margin: 0; color: var(--muted); }
.summary { display: flex; flex-wrap: wrap; gap: 0.4rem 1rem; }
.summary code { overflow-wrap: anywhere; }
.index { list-style: none; padding: 0; margin: 0; }
.index li { margin: 0.7rem 0; }
.terminal-label { font-size: 1.05rem; margin: 0; }
@media (max-width: 42rem) {
  .chunk, .views, .term dl { grid-template-columns: 1fr; }
  h1 { font-size: 1.45rem; }
  main { padding-inline: 0.7rem; }
}
"""


def render_cassette(c: PartialCassette) -> str:
    """Return a self-contained HTML page for one cassette."""
    rows, tail = _chunk_views(c.chunks)
    body = "\n".join(
        [
            "<main>",
            _header_html(c),
            _termination_html(c.termination),
            "<section>",
            "<h2>Chunks</h2>",
            "".join(_chunk_html(row) for row in rows),
            _terminal_html(c.termination, tail),
            "</section>",
            _summary_html(c),
            "</main>",
        ]
    )
    return _document(c.id, body)


def render_index(items: Sequence[tuple[str, PartialCassette]]) -> str:
    """Return an index page. Each item is an href plus the cassette it names."""
    cards: list[str] = []
    for href, cassette in items:
        state = cassette.termination.state
        cards.append(
            '<li class="card">'
            f'<p><a href="{_esc(href)}">{_esc(cassette.id)}</a> '
            f'<span class="pill term-{state}">{_esc(state)}</span> '
            f"<span>{_esc(cassette.cls)}</span></p>"
            f'<p class="desc">{_esc(cassette.description)}</p>'
            "</li>"
        )
    listing = "\n".join(cards) if cards else '<li class="card"><p>No cassettes.</p></li>'
    body = (
        "<main>"
        '<p class="eyebrow">partial stream</p>'
        "<h1>Cassettes</h1>"
        f'<p class="meta">{len(items)} cassette(s)</p>'
        f'<ul class="index">{listing}</ul>'
        "</main>"
    )
    return _document("Partial stream cassettes", body)


def bind_server(directory: Path, port: int) -> socketserver.TCPServer:
    """Listen on 127.0.0.1 for a rendered site. Port 0 chooses a free port."""
    root = str(directory)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

    def handler(
        request: object,
        client_address: object,
        server: socketserver.BaseServer,
    ) -> Handler:
        if not isinstance(request, socket.socket):
            raise TypeError("HTTP request must be a socket")
        return Handler(request, client_address, server, directory=root)

    return http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)


def write_site(cassettes: Sequence[PartialCassette], out_dir: Path) -> Path:
    """Write ``index.html`` and one page per cassette. Return the index path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    items: list[tuple[str, PartialCassette]] = []
    pages: list[tuple[str, str]] = []
    for position, cassette in enumerate(sorted(cassettes, key=lambda item: item.id), start=1):
        href = _href_for(cassette.id, position)
        items.append((href, cassette))
        pages.append((href, render_cassette(cassette)))
    root = out_dir.resolve()
    # Resolve and contain every destination, the index included, before writing anything,
    # so a pre-existing symlink in the output directory can never redirect a write outside.
    writes = [(_within(out_dir, root, href), page) for href, page in pages]
    index_path = _within(out_dir, root, "index.html")
    for destination, page in writes:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(page, encoding="utf-8")
    index_path.write_text(render_index(items), encoding="utf-8")
    return out_dir / "index.html"


def _document(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_esc(title)}</title>\n"
        f"<style>{_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )


def _header_html(c: PartialCassette) -> str:
    method = c.request.get("method", "")
    url = c.request.get("url", "")
    header_rows = "".join(
        f'<tr><th scope="row">{_esc(name)}</th><td>{_esc(value)}</td></tr>'
        for name, value in c.headers
    )
    if not header_rows:
        header_rows = '<tr><td colspan="2">No headers</td></tr>'
    return (
        '<header class="card">'
        '<p class="eyebrow">partial stream</p>'
        f"<h1>{_esc(c.id)}</h1>"
        f'<p class="meta">class <code>{_esc(c.cls)}</code></p>'
        f'<p class="desc">{_esc(c.description)}</p>'
        f'<p class="request"><span class="method">{_esc(method)}</span> '
        f'<span class="url">{_esc(url)}</span></p>'
        f'<p class="status">status <strong>{c.status}</strong></p>'
        "<table>"
        '<thead><tr><th scope="col">Header</th><th scope="col">Value</th></tr></thead>'
        f"<tbody>{header_rows}</tbody>"
        "</table>"
        "</header>"
    )


def _termination_html(termination: Termination) -> str:
    state = termination.state
    return (
        f'<section class="term term-{state}" data-termination="{_esc(state)}">'
        f'<p class="state-label">{_esc(state)}</p>'
        "<dl>"
        f"<dt>after_chunk</dt><dd>{termination.after_chunk}</dd>"
        f"<dt>error</dt><dd>{_esc(_or_dash(termination.error))}</dd>"
        f'<dt>detail</dt><dd class="detail">{_esc(_or_dash(termination.detail))}</dd>'
        "</dl>"
        "</section>"
    )


def _terminal_html(termination: Termination, tail: bytes) -> str:
    label = _esc(_terminal_line(termination))
    tail_html = ""
    if tail:
        badges = "".join(f'<span class="hex-badge">{byte:02x}</span>' for byte in tail)
        tail_html = f'<p class="tail" data-tail-hex="{tail.hex()}">undecodable tail {badges}</p>'
    return (
        f'<article class="terminal term-{termination.state}">'
        f'<p class="terminal-label">{label}</p>'
        f"{tail_html}"
        "</article>"
    )


def _terminal_line(termination: Termination) -> str:
    if termination.state == "clean_close":
        return "■ clean close"
    if termination.state == "early_close":
        return f"✂ connection reset: {termination.error or ''}"
    return f"⋯ truncated mid-event: {termination.detail or ''}"


def _summary_html(c: PartialCassette) -> str:
    digest = hashlib.sha256(c.body()).hexdigest()
    return (
        '<footer class="card summary">'
        f"<span>total bytes <strong>{len(c.body())}</strong></span>"
        f"<span>chunk count <strong>{len(c.chunks)}</strong></span>"
        f"<span>body sha256 <code>{digest}</code></span>"
        "</footer>"
    )


def _chunk_html(view: "_ChunkView") -> str:
    badges: list[str] = []
    if view.completes_split:
        badges.append('<span class="badge complete">completes split codepoint</span>')
    if view.carries:
        unit = "byte" if view.carries == 1 else "bytes"
        badges.append(f'<span class="badge carry">↪ carries {view.carries} {unit}</span>')
    text = '<p class="empty">(empty chunk)</p>' if view.empty else _tokens_html(view.tokens)
    length = "1 byte" if view.length == 1 else f"{view.length} bytes"
    return (
        f'<article class="chunk" data-chunk-index="{view.index}" data-hex="{view.continuous_hex}">'
        f'<div class="chunk-index">{view.index}</div>'
        '<div class="chunk-body">'
        '<p class="chunk-meta">'
        f'<span class="length">{length}</span> '
        f'<span class="range">offset {view.start}–{view.end}</span> '
        f"{''.join(badges)}"
        "</p>"
        '<div class="views">'
        f'<pre class="hex">{_esc(view.grouped_hex)}</pre>'
        f'<div class="text">{text}</div>'
        "</div>"
        "</div>"
        "</article>"
    )


@dataclass(frozen=True)
class _ChunkView:
    index: int
    length: int
    start: int
    end: int
    grouped_hex: str
    continuous_hex: str
    tokens: list["_Text | _Hex"]
    carries: int
    completes_split: bool
    empty: bool


@dataclass(frozen=True)
class _Text:
    value: str


@dataclass(frozen=True)
class _Hex:
    value: bytes


def _chunk_views(chunks: Sequence[Chunk]) -> tuple[list[_ChunkView], bytes]:
    carry = b""
    views: list[_ChunkView] = []
    offset = 0
    for chunk in chunks:
        tokens, carry_out = _scan(carry + chunk.data)
        completes = (
            bool(carry)
            and bool(tokens)
            and isinstance(tokens[0], _Text)
            and tokens[0].value.encode("utf-8").startswith(carry)
        )
        views.append(
            _ChunkView(
                chunk.index,
                len(chunk.data),
                offset,
                offset + len(chunk.data),
                _grouped_hex(chunk.data),
                chunk.data.hex(),
                tokens,
                len(carry_out) if chunk.data and carry_out else 0,
                completes,
                not chunk.data,
            )
        )
        carry = carry_out
        offset += len(chunk.data)
    return views, carry


def _scan(data: bytes) -> tuple[list[_Text | _Hex], bytes]:
    """Tokenize complete UTF-8 and invalid bytes, retaining only a valid prefix tail."""
    tokens: list[_Text | _Hex] = []
    text: list[str] = []
    index = 0
    while index < len(data):
        lead = data[index]
        length = 0
        if lead < 0x80:
            length = 1
        elif 0xC2 <= lead <= 0xDF:
            length = 2
        elif 0xE0 <= lead <= 0xEF:
            length = 3
        elif 0xF0 <= lead <= 0xF4:
            length = 4
        if length:
            piece = data[index : index + length]
            if len(piece) < length:
                low, high = {
                    0xE0: (0xA0, 0xBF),
                    0xED: (0x80, 0x9F),
                    0xF0: (0x90, 0xBF),
                    0xF4: (0x80, 0x8F),
                }.get(lead, (0x80, 0xBF))
                if all(
                    (low <= byte <= high) if offset == 1 else (0x80 <= byte <= 0xBF)
                    for offset, byte in enumerate(piece[1:], start=1)
                ):
                    break
            else:
                try:
                    decoded = piece.decode("utf-8")
                except UnicodeDecodeError:
                    pass
                else:
                    text.append(decoded)
                    index += length
                    continue
        if text:
            tokens.append(_Text("".join(text)))
            text.clear()
        tokens.append(_Hex(data[index : index + 1]))
        index += 1
    if text:
        tokens.append(_Text("".join(text)))
    return tokens, data[index:]


def _tokens_html(tokens: Sequence[_Text | _Hex]) -> str:
    parts: list[str] = []
    for token in tokens:
        if isinstance(token, _Text):
            parts.append(f'<span class="run">{_esc(_visible(token.value))}</span>')
        else:
            parts.append(f'<span class="hex-badge">{token.value.hex()}</span>')
    return "".join(parts)


def _visible(text: str) -> str:
    return "".join(_visible_char(char) for char in text)


def _visible_char(char: str) -> str:
    code = ord(char)
    if code < 32:
        return chr(0x2400 + code)
    if code == 127:
        return "\u2421"
    if 0x80 <= code <= 0x9F:
        return f"[U+{code:04X}]"
    return char


def _grouped_hex(data: bytes) -> str:
    words = [f"{byte:02x}" for byte in data]
    groups = [" ".join(words[index : index + 4]) for index in range(0, len(words), 4)]
    return "  ".join(groups)


def _or_dash(value: str | None) -> str:
    return value if value else "—"


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _href_for(cassette_id: str, position: int) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", cassette_id).strip(".-")[:80] or "cassette"
    return f"pages/{position:03d}-{slug}.html"


def _within(out_dir: Path, root: Path, href: str) -> Path:
    destination = (out_dir / href).resolve()
    if not destination.is_relative_to(root):
        raise ValueError(f"refusing to write outside {out_dir}")
    return destination
