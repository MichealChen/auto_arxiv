from __future__ import annotations

from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen
import json
import mimetypes
import re

from .config import AppConfig, load_config
from .store import (
    find_paper_in_data,
    load_daily_recommendations,
    load_history,
    load_latest_recommendations,
    load_user_state,
    update_user_state,
)
from .workflow import generate_recommendations


def serve(config_path: Path, host: str, port: int, public_dir: Path | None = None) -> None:
    server = create_server(config_path=config_path, host=host, port=port, public_dir=public_dir)
    url = f"http://{host}:{server.server_address[1]}"
    print(f"auto_arxiv is running at {url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping auto_arxiv.")
    finally:
        server.server_close()


def create_server(
    config_path: Path,
    host: str,
    port: int,
    public_dir: Path | None = None,
) -> ThreadingHTTPServer:
    config = load_config(config_path)
    public_dir = (public_dir or Path("public")).resolve()
    if not public_dir.exists():
        raise FileNotFoundError("Missing public/ directory. Cannot start the web app.")

    handler = _build_handler(config_path=config_path, config=config, public_dir=public_dir)
    return ThreadingHTTPServer((host, port), handler)


def _build_handler(config_path: Path, config: AppConfig, public_dir: Path):
    class AutoArxivHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(public_dir), **kwargs)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/api/status":
                self._send_json({"ok": True, "profile": config.profile.name})
                return
            if path == "/api/recommendations":
                self._send_json(load_latest_recommendations(config.output.data_directory))
                return
            if path.startswith("/api/recommendations/"):
                date = unquote(path.rsplit("/", 1)[-1])
                self._send_json(load_daily_recommendations(config.output.data_directory, date))
                return
            if path == "/api/history":
                self._send_json(load_history(config.output.data_directory))
                return
            if path == "/api/state":
                self._send_json(load_user_state(config.output.data_directory))
                return
            if path.startswith("/api/download/"):
                arxiv_id = unquote(path.rsplit("/", 1)[-1])
                self._download_pdf(arxiv_id)
                return
            if path.startswith("/data/"):
                self._serve_data_file(path)
                return

            super().do_GET()

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/refresh":
                fresh_config = load_config(config_path)
                result = generate_recommendations(fresh_config)
                self._send_json(
                    {
                        "ok": True,
                        "profile": result.profile_name,
                        "fetched": result.fetched_count,
                        "matched": result.ranked_count,
                        "selected": result.selected_count,
                        "data_path": str(result.data_path),
                        "markdown_path": str(result.markdown_path),
                    }
                )
                return
            if parsed.path == "/api/state":
                body = self._read_json_body()
                arxiv_id = str(body.get("arxiv_id", ""))
                if not arxiv_id:
                    self.send_error(HTTPStatus.BAD_REQUEST, "Missing arXiv id")
                    return
                state = update_user_state(
                    config.output.data_directory,
                    arxiv_id=arxiv_id,
                    values=body,
                )
                self._send_json(state)
                return

            self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")

        def log_message(self, format: str, *args) -> None:
            print(f"[auto_arxiv] {self.address_string()} - {format % args}")

        def _send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))

        def _serve_data_file(self, request_path: str) -> None:
            relative = Path(unquote(request_path.removeprefix("/data/")))
            if relative.is_absolute() or ".." in relative.parts:
                self.send_error(HTTPStatus.BAD_REQUEST, "Invalid data path")
                return

            file_path = (config.output.data_directory / relative).resolve()
            data_root = config.output.data_directory.resolve()
            if not _is_relative_to(file_path, data_root) or not file_path.exists():
                self.send_error(HTTPStatus.NOT_FOUND, "Data file not found")
                return

            body = file_path.read_bytes()
            content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _download_pdf(self, arxiv_id: str) -> None:
            safe_id = _safe_arxiv_id(arxiv_id)
            if safe_id != arxiv_id:
                self.send_error(HTTPStatus.BAD_REQUEST, "Invalid arXiv id")
                return

            paper = find_paper_in_data(config.output.data_directory, arxiv_id)
            if paper is None or not paper.get("pdf_url"):
                self.send_error(HTTPStatus.NOT_FOUND, "Paper PDF not found in local data")
                return

            config.output.download_directory.mkdir(parents=True, exist_ok=True)
            pdf_path = config.output.download_directory / f"{safe_id}.pdf"
            if not pdf_path.exists():
                request = Request(
                    str(paper["pdf_url"]),
                    headers={"User-Agent": "auto-arxiv/0.1"},
                )
                with urlopen(request, timeout=60) as response:
                    pdf_path.write_bytes(response.read())

            body = pdf_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f'attachment; filename="{safe_id}.pdf"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return AutoArxivHandler


def _safe_arxiv_id(value: str) -> str:
    if re.fullmatch(r"[0-9]{4}\.[0-9]{4,5}(v[0-9]+)?", value):
        return value
    if re.fullmatch(r"[a-zA-Z.-]+/[0-9]{7}(v[0-9]+)?", value):
        return value.replace("/", "_")
    return ""


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
