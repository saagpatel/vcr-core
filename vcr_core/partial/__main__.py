"""Validate, count, inspect, or serve partial-stream cassettes."""

import argparse
import socketserver
import sys
import tempfile
import threading
from collections.abc import Sequence
from pathlib import Path

from . import iter_fixtures, load
from .cassette import PartialCassette
from .inspect import bind_server, write_site


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate files or directories recursively")
    validate.add_argument("paths", nargs="+", type=Path)

    commands.add_parser("count", help="count bundled fixtures by class")

    source = argparse.ArgumentParser(add_help=False)
    source.add_argument("paths", nargs="*", type=Path)
    source.add_argument(
        "--bundled",
        action="store_true",
        help="use the bundled fixtures instead of paths",
    )

    inspect = commands.add_parser(
        "inspect",
        parents=[source],
        help="write an HTML site for cassettes",
    )
    inspect.add_argument(
        "--out",
        type=Path,
        default=Path("partial-inspect"),
        help="output directory (default: ./partial-inspect)",
    )

    serve = commands.add_parser(
        "serve",
        parents=[source],
        help="render a site and serve it on 127.0.0.1",
    )
    serve.add_argument("--port", type=_port, default=8765, help="port (default: 8765; 0 = auto)")

    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "count":
        return _count()
    if args.command == "validate":
        return _validate(args.paths)
    if args.command == "inspect":
        return _inspect(args.paths, bundled=args.bundled, out=args.out)
    return _serve(args.paths, bundled=args.bundled, port=args.port)


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if port < 0 or port > 65535:
        raise argparse.ArgumentTypeError("port must be in 0..65535")
    return port


def _count() -> int:
    counts = dict.fromkeys(("split_codepoint", "partial_event", "early_close"), 0)
    for cassette in iter_fixtures():
        counts[cassette.cls] += 1
    print(
        " ".join(f"{kind}={count}" for kind, count in counts.items()),
        f"total={sum(counts.values())}",
    )
    return 0


def _validate(paths: Sequence[Path]) -> int:
    failed = False
    for path in paths:
        candidates = sorted(path.glob("**/*.pcas.json")) if path.is_dir() else [path]
        for candidate in candidates:
            try:
                load(candidate)
            except (OSError, ValueError) as exc:
                print(f"{candidate}: {exc}", file=sys.stderr)
                failed = True
    return int(failed)


def _inspect(paths: Sequence[Path], *, bundled: bool, out: Path) -> int:
    cassettes = _load_sources(paths, bundled=bundled)
    if cassettes is None:
        return 1
    index = write_site(cassettes, out)
    print(index)
    return 0


def _serve(paths: Sequence[Path], *, bundled: bool, port: int) -> int:
    cassettes = _load_sources(paths, bundled=bundled)
    if cassettes is None:
        return 1
    with tempfile.TemporaryDirectory(prefix="partial-inspect-") as tmp:
        root = Path(tmp)
        write_site(cassettes, root)
        server = bind_server(root, port)
        worker = threading.Thread(
            target=server.serve_forever,
            name="partial-inspect-http",
            daemon=True,
        )
        worker.start()
        host, bound = _bound_address(server)
        print(f"http://{host}:{bound}/index.html", flush=True)
        try:
            while worker.is_alive():
                worker.join(timeout=0.2)
        except KeyboardInterrupt:
            return 0
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)
    return 0


def _bound_address(server: socketserver.TCPServer) -> tuple[str, int]:
    host = server.server_address[0]
    bound = server.server_address[1]
    if isinstance(host, str):
        return host, bound
    raise RuntimeError("HTTP server did not bind an IPv4 address")


def _load_sources(paths: Sequence[Path], *, bundled: bool) -> list[PartialCassette] | None:
    if bundled and paths:
        print("pass paths or --bundled, not both", file=sys.stderr)
        return None
    if bundled:
        return list(iter_fixtures())
    if not paths:
        print("pass cassette paths or --bundled", file=sys.stderr)
        return None
    loaded: list[PartialCassette] = []
    failed = False
    for path in paths:
        candidates = sorted(path.glob("**/*.pcas.json")) if path.is_dir() else [path]
        for candidate in candidates:
            try:
                loaded.append(load(candidate))
            except (OSError, ValueError) as exc:
                print(f"{candidate}: {exc}", file=sys.stderr)
                failed = True
    if failed:
        return None
    return loaded


if __name__ == "__main__":
    sys.exit(main())
