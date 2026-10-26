"""A stand-in for the few GitHub addresses the installers use, serving one release from a folder.

    python tests/fake_github.py PORT FOLDER VERSION

FOLDER holds the release's files: install.sh, install.ps1 and the package. The installers are
pointed at it with RACKSIDE_REPO=http://127.0.0.1:PORT. It answers:

    /releases/latest/download/NAME       redirect to the file of the latest release, as GitHub does
    /releases/download/vVERSION/NAME     the file
    anything else                        404, which is what an unknown release gets on GitHub too
"""

from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main(argv: list[str]) -> None:
    port, folder, version = int(argv[1]), Path(argv[2]), argv[3]
    tag = f"v{version}"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.answer(body=True)

        def do_HEAD(self) -> None:
            # uv asks for the headers first, to see whether the file can be fetched in pieces.
            self.answer(body=False)

        def answer(self, body: bool) -> None:
            path = self.path.split("?")[0]
            latest = "/releases/latest/download/"
            if path.startswith(latest):
                self.send_response(302)
                self.send_header("Location", f"/releases/download/{tag}/{path[len(latest):]}")
                self.end_headers()
                return
            own = f"/releases/download/{tag}/"
            file = folder / path[len(own):] if path.startswith(own) else None
            if file is None or "/" in path[len(own):] or not file.is_file():
                self.send_error(404)
                return
            content = file.read_bytes()
            self.send_response(200)
            # GitHub serves release files like this, scripts included.
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            if body:
                self.wfile.write(content)

        def log_message(self, *args) -> None:
            sys.stderr.write("fake github: " + (args[0] % args[1:]) + "\n")

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main(sys.argv)
