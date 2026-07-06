from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path

from .config import AppConfig, load_config
from .server import serve
from .workflow import generate_recommendations


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "recommend":
        return _recommend(args.config)
    if args.command == "serve":
        serve(
            config_path=args.config,
            host=args.host,
            port=args.port,
            public_dir=args.public_dir,
        )
        return 0

    parser.print_help()
    return 1


def _build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="auto-arxiv")
    subparsers = parser.add_subparsers(dest="command")

    recommend = subparsers.add_parser("recommend", help="Generate today's arXiv recommendations.")
    recommend.add_argument(
        "--config",
        type=Path,
        default=Path("config.toml"),
        help="Path to a TOML config file. Defaults to config.toml.",
    )

    serve_parser = subparsers.add_parser("serve", help="Start the local recommendation web app.")
    serve_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.toml"),
        help="Path to a TOML config file. Defaults to config.toml.",
    )
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    serve_parser.add_argument("--port", type=int, default=8765, help="Port to bind.")
    serve_parser.add_argument(
        "--public-dir",
        type=Path,
        default=Path("public"),
        help="Path to the web app static files.",
    )

    return parser


def _recommend(config_path: Path) -> int:
    config = load_config(config_path)
    result = generate_recommendations(config)

    _print_summary(config, result)
    return 0


def _print_summary(config: AppConfig, result) -> None:
    print(f"Profile: {config.profile.name}")
    print(f"Fetched: {result.fetched_count}")
    print(f"Matched: {result.ranked_count}")
    print(f"Selected: {result.selected_count}")
    print(f"Report: {result.markdown_path}")
    print(f"Data: {result.data_path}")
