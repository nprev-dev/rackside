"""Pictures of Rackside with made-up data for the readme: two screenshots and the animated centrepiece.

    python tools/record.py                 everything, into docs/
    python tools/record.py animation       only docs/centrepiece.webp
    python tools/record.py screenshots     only docs/overview.png and docs/alerts.png

Needs Firefox and Pillow (python -m pip install pillow). It starts tools/demo.py and a headless
Firefox of its own, drives Firefox over its Marionette protocol (built into Firefox, nothing to
install), and stops both at the end. The page's clock is stepped one frame at a time, so the
animation is smooth however slowly the pictures are taken.
"""

from __future__ import annotations

import base64
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
WIDTH, HEIGHT = 1920, 1080
# The animation: seconds, frames a second, and how much the page has settled before it starts.
SECONDS, FPS, SETTLE = 8, 25, 20
# Seconds over which the end of the animation fades back into its start, and the WebP quality.
LOOP_BLEND, QUALITY = 0.5, 75


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class Marionette:
    """Just enough of Firefox's remote-control protocol: length-prefixed JSON over a socket."""

    def __init__(self, port: int):
        for _ in range(120):
            try:
                self.sock = socket.create_connection(("127.0.0.1", port), timeout=60)
                break
            except OSError:
                time.sleep(0.5)
        else:
            raise SystemExit("Firefox did not open its remote-control port")
        self.ids = iter(range(1, 1 << 30))
        self._read()

    def _read(self):
        length = b""
        while not length.endswith(b":"):
            length += self.sock.recv(1)
        size, data = int(length[:-1]), b""
        while len(data) < size:
            data += self.sock.recv(size - len(data))
        return json.loads(data)

    def call(self, command: str, params: dict | None = None):
        message = json.dumps([0, next(self.ids), command, params or {}]).encode()
        self.sock.sendall(str(len(message)).encode() + b":" + message)
        while True:
            answer = self._read()
            if isinstance(answer, list) and answer[0] == 1:
                if answer[2]:
                    raise RuntimeError(f"{command}: {answer[2].get('message', answer[2])}")
                return answer[3]

    def script(self, source: str, *args):
        return self.call("WebDriver:ExecuteScript", {"script": source, "args": list(args)}).get("value")

    def wait_for(self, source: str):
        """Runs a script that ends by calling its last argument, and waits for that."""
        return self.call("WebDriver:ExecuteAsyncScript", {"script": source, "args": [], "scriptTimeout": 120000}).get("value")

    def picture(self, element: str | None = None):
        from PIL import Image

        params: dict = {"full": False, "hash": False}
        if element:
            found = self.call("WebDriver:FindElement", {"using": "css selector", "value": element})["value"]
            params["id"] = next(iter(found.values()))
        return Image.open(io.BytesIO(base64.b64decode(self.call("WebDriver:TakeScreenshot", params)["value"]))).convert("RGB")


def start_firefox(port: int) -> tuple[subprocess.Popen, Path]:
    # A Firefox installed as a snap (Ubuntu's /usr/bin/firefox only starts the snap) may only use
    # profiles inside its own folder.
    snap = Path.home() / "snap" / "firefox" / "common"
    profile = Path(tempfile.mkdtemp(prefix="rackside-record-", dir=snap if snap.is_dir() else None))
    prefs = [f'marionette.port", {port}', 'browser.shell.checkDefaultBrowser", false', 'app.update.auto", false', 'toolkit.telemetry.enabled", false',
             'datareporting.policy.dataSubmissionEnabled", false', 'datareporting.healthreport.uploadEnabled", false',
             'browser.safebrowsing.malware.enabled", false', 'browser.safebrowsing.phishing.enabled", false', 'network.captive-portal-service.enabled", false',
             'network.connectivity-service.enabled", false', 'ui.prefersReducedMotion", 0', 'layout.css.devPixelsPerPx", "1.0"']
    (profile / "user.js").write_text("".join(f'user_pref("{pref});\n' for pref in prefs))
    process = subprocess.Popen(["firefox", "--headless", "--marionette", "--no-remote", "--profile", str(profile)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return process, profile


def open_page(firefox: Marionette, demo: int, scenario: str, seconds: int) -> None:
    firefox.call("WebDriver:Navigate", {"url": f"http://127.0.0.1:{demo}/?record=1"})
    loaded = firefox.wait_for(f"const done = arguments[arguments.length - 1]; window.__record.load({json.dumps(scenario)}, {seconds}).then(done);")
    if loaded != seconds:
        raise SystemExit(f"the demo gave {loaded} seconds of data, not {seconds}")
    # Let it settle: everything fades in and the numbers roll to their values before any picture.
    firefox.script(f"for (let i = 0; i < {SETTLE * FPS}; i += 1) window.__record.step({1000 / FPS});")


def screenshots(firefox: Marionette, demo: int) -> None:
    for scenario, name in (("demo", "overview"), ("alerts", "alerts")):
        open_page(firefox, demo, scenario, SETTLE + 2)
        firefox.picture().save(DOCS / f"{name}.png", optimize=True)
        print(f"docs/{name}.png")


def animation(firefox: Marionette, demo: int, quality: int = QUALITY, keep: Path | None = None) -> None:
    from PIL import Image

    count, blend = SECONDS * FPS, round(FPS * LOOP_BLEND)
    open_page(firefox, demo, "demo", SETTLE + SECONDS + 3)
    frames = []
    for _ in range(count + blend):
        firefox.script(f"window.__record.step({1000 / FPS});")
        frames.append(firefox.picture(".hero"))
    # The loop: its first frames are what comes after the last, fading into the real start. Played
    # round and round, the end runs on into the beginning without a jump.
    looped = [Image.blend(frames[count + index], frames[index], index / blend) if index < blend else frames[index] for index in range(count)]
    target = keep or DOCS / "centrepiece.webp"
    looped[0].save(target, save_all=True, append_images=looped[1:], duration=round(1000 / FPS), loop=0, quality=quality, method=6)
    print(f"{target.name}: {len(looped)} frames, {target.stat().st_size // 1024} KB")


def main(argv: list[str]) -> int:
    wanted = argv[1:] or ["screenshots", "animation"]
    demo_port, firefox_port = free_port(), free_port()
    demo = subprocess.Popen([sys.executable, str(ROOT / "tools" / "demo.py"), "--port", str(demo_port)], stdout=subprocess.DEVNULL)
    process, profile = start_firefox(firefox_port)
    firefox = None
    try:
        firefox = Marionette(firefox_port)
        firefox.call("WebDriver:NewSession", {"capabilities": {}})
        for _ in range(60):
            try:
                socket.create_connection(("127.0.0.1", demo_port), timeout=1).close()
                break
            except OSError:
                time.sleep(0.5)
        # Firefox starts on a page of its own, where pages' scripts do not run; the demo's first.
        firefox.call("WebDriver:Navigate", {"url": f"http://127.0.0.1:{demo_port}/demo/snapshot?tick=0"})
        # The window is the screen the pictures show: make its inside exactly WIDTH x HEIGHT.
        firefox.call("WebDriver:SetWindowRect", {"width": WIDTH, "height": HEIGHT})
        inner = firefox.script("return [innerWidth, innerHeight];")
        firefox.call("WebDriver:SetWindowRect", {"width": 2 * WIDTH - inner[0], "height": 2 * HEIGHT - inner[1]})
        if "screenshots" in wanted:
            screenshots(firefox, demo_port)
        if "animation" in wanted:
            animation(firefox, demo_port)
    finally:
        if firefox:
            try:
                firefox.call("Marionette:Quit", {"flags": ["eForceQuit"]})
            except Exception:
                pass
        try:
            process.wait(20)
        except subprocess.TimeoutExpired:
            process.kill()
        demo.terminate()
        shutil.rmtree(profile, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
