"""Rackside with made-up data: for screenshots, the animation in the readme, and a look without one's own machine.

    python tools/demo.py                     the page at http://127.0.0.1:8799, the demo scenario
    python tools/demo.py --scenario alerts   with things going wrong
    python tools/demo.py --port 9000

It is the real dashboard; only what the three collectors would read is made up: a server called
"atlas" on 192.168.1.0/24 with a few well-known containers. It sends nothing onto the network.

For recording (see tools/record.py) the page can be opened as /?record=1. Its clock then only moves
when told to, a frame at a time, and each second of data is fetched ahead from /demo/snapshot?tick=N,
so every frame is exactly what the page would show at that moment, however long a picture takes.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
GIB, MIB = 1024**3, 1024**2
H, M = 3600, 60
# The moment the made-up machine's clock shows at tick 0: 21:42:05 on 2026-10-27, local time.
NOW = time.mktime((2026, 10, 27, 21, 42, 5, 0, 0, -1))


def noise(k: float) -> float:
    """A smooth wobble between 0 and 1, the same for the same k."""
    return 0.5 + 0.25 * math.sin(k * 1.7) + 0.15 * math.sin(k * 0.61 + 1.3) + 0.1 * math.sin(k * 3.1 + 0.4)


def wob(base: float, tick: int, share: float = 0.25) -> float:
    return base * (1 - share + 2 * share * noise(tick * 0.9))


# --- containers -------------------------------------------------------------------------------

def container(index, tick, name, image, ports, cpu, mem, rx, tx, status, state="running", health=None):
    running = state == "running"
    return {
        "id": f"{index:02x}c0ffee{index:04x}",
        "name": name,
        "image": image,
        "state": state,
        "status": status,
        "health": health,
        "project": None,
        "ports": [{"host": host, "container": inside, "proto": proto} for host, inside, proto in ports],
        "cpu_percent": round(wob(cpu, tick + index * 7), 2) if running else None,
        "cpu_count": 16 if running else None,
        "mem_used": int(mem * MIB * (0.97 + 0.03 * noise(tick + index))) if running else None,
        "mem_limit": 62 * GIB if running else None,
        "mem_percent": round(mem * MIB / (62 * GIB) * 100, 2) if running else None,
        "net_rx_bps": round(wob(rx, tick + index * 3)) if running else None,
        "net_tx_bps": round(wob(tx, tick + index * 5)) if running else None,
        "net_rx_bytes": None,
        "net_tx_bytes": None,
        "blk_read_bytes": None,
        "blk_write_bytes": None,
        "pids": 12 + index if running else None,
    }


def containers(tick: int, alerts: bool = False) -> dict:
    items = [
        container(1, tick, "caddy", "caddy:2.10.2", [(80, 80, "tcp"), (443, 443, "tcp")], 0.4, 38, 410_000, 2_900_000, "Up 12 days"),
        container(2, tick, "grafana", "grafana/grafana:12.1.1", [(3000, 3000, "tcp")], 0.8, 160, 21_000, 95_000, "Up 3 hours"),
        container(3, tick, "jellyfin", "jellyfin/jellyfin:10.11.0", [(8096, 8096, "tcp")], 17.5, 1450, 260_000, 18_400_000, "Up 12 days (healthy)", health="healthy"),
        container(4, tick, "nextcloud", "nextcloud:31.0.8", [(8080, 80, "tcp")], 1.2, 420, 1_900_000, 180_000, "Up 12 days"),
        container(5, tick, "ollama", "ollama/ollama:0.12.3", [(11434, 11434, "tcp")], 0.2, 5900, 1_200, 800, "Up 6 hours"),
        container(6, tick, "pihole", "pihole/pihole:2025.08.0", [(53, 53, "tcp"), (53, 53, "udp"), (8053, 80, "tcp")], 0.6, 92, 34_000, 41_000,
                  "Up 12 days (unhealthy)" if alerts else "Up 12 days (healthy)", health="unhealthy" if alerts else "healthy"),
        container(7, tick, "postgres", "postgres:17.6", [], 0.9, 310, 52_000, 47_000, "Up 12 days"),
        container(8, tick, "vaultwarden", "vaultwarden/server:1.34.3", [(8222, 80, "tcp")], 0.1, 58, 3_000, 9_000, "Up 12 days"),
        container(9, tick, "backup-nightly", "restic/restic:0.18.0", [], 0, 0, 0, 0, "Exited (0) 10 hours ago", state="exited"),
    ]
    states: dict[str, int] = {}
    for item in items:
        states[item["state"]] = states.get(item["state"], 0) + 1
    return {"ok": True, "error": None, "total": len(items), "states": states, "items": items}


# --- network ----------------------------------------------------------------------------------

def network(tick: int, alerts: bool = False) -> dict:
    span = 240

    def tx(i):
        j = i % 101
        if j < 38:
            return round(0.5e6 + 1.0e6 * noise(i * 3) + (5e6 if j in (9, 10, 27) else 0))
        if j < 46:
            return round(24e6 + 7e6 * noise(i * 5))
        return round(13e6 + 5e6 * noise(i * 7) + (10e6 if j % 9 < 2 else 0))

    def rx(i):
        j = i % 97
        if 12 <= j < 34:
            return round(3.2e6 + 1.4e6 * noise(i * 13))
        if j >= 80:
            return round(2.0e6 + 0.9e6 * noise(i * 17))
        return round(0.2e6 + 0.45e6 * noise(i * 11) + (1.3e6 if j in (52, 71) else 0))

    first = tick - span
    txs, rxs = [tx(i) for i in range(first, tick)], [rx(i) for i in range(first, tick)]
    gateway = [round(0.19 + 0.12 * noise(i * 3) + (0.45 if i % 49 == 0 else 0), 2) for i in range(tick - 120, tick)]
    internet = [round(11.6 + 2.6 * noise(i * 7) + (12.5 if i % 57 == 0 else 0), 2) for i in range(tick - 120, tick)]
    if alerts:
        internet = internet[:-3] + [None, None, None]
    answered = [value for value in internet if value is not None]
    talkers = [("192.168.1.42", 61_000, 18_300_000, 2), ("192.168.1.60", 2_250_000, 240_000, 3), ("100.64.0.12", 38_000, 2_700_000, 1),
               ("198.51.100.27", 410_000, 22_000, 4), ("203.0.113.80", 9_800, 4_100, 1)]
    return {
        "ok": True, "error": None, "gateway": "192.168.1.1",
        "link": {"name": "enp3s0", "state": "up", "speed": 2500, "duplex": "full", "mtu": 1500, "mac": "02:42:9a:1c:5e:10", "flaps": 0,
                 "rx_errs": 0, "tx_errs": 0, "rx_drop": 12, "tx_drop": 0, "address": "192.168.1.20"},
        "rx_bps": rxs[-1], "tx_bps": txs[-1], "history": {"rx": rxs, "tx": txs},
        "totals": {"boot": {"rx": int(88.4 * GIB), "tx": int(1.31 * 1024 * GIB)},
                   "today": {"rx": int(6.2 * GIB), "tx": int(71.5 * GIB), "since": NOW - 15 * H, "whole_day": True}},
        "sockets": {"tcp_estab": 46, "tcp_listen": 17, "tcp_time_wait": 9, "tcp_other": 3, "udp": 21},
        "listening": [
            {"port": 22, "proto": "tcp", "scope": "*", "who": "ssh"},
            {"port": 41641, "proto": "udp", "scope": "*", "who": "tailscaled"},
            {"port": 631, "proto": "tcp", "scope": "lo", "who": "cups"},
            {"port": 8787, "proto": "tcp", "scope": "lo", "who": "rackside"},
            {"port": 9100, "proto": "tcp", "scope": "ts", "who": "node_exporter"},
        ],
        "talkers": [{"host": host, "rx_bps": round(wob(r, tick + i)), "tx_bps": round(wob(t, tick + i + 2)), "conns": conns}
                    for i, (host, r, t, conns) in enumerate(talkers)],
        "ping": [
            {"name": "gateway", "host": "192.168.1.1", "interval": 1.0, "last": gateway[-1], "avg": round(sum(gateway) / len(gateway), 2),
             "max": max(gateway), "loss": 0.0, "history": gateway, "error": None},
            {"name": "internet", "host": "1.1.1.1", "interval": 30.0, "last": internet[-1], "avg": round(sum(answered) / len(answered), 2),
             "max": max(answered), "loss": 2.5 if alerts else 0.0, "history": internet, "error": None},
        ],
        "dns": {"server": "192.168.1.1", "ms": 0.38, "ok": True, "error": None},
        "wan": {"ip": "203.0.113.42", "since": NOW - 19 * 86400 - 4 * H, "previous": None, "checked": NOW - 240, "error": None},
        "speedtest": {"enabled": True, "running": False, "last": {"ts": NOW - 80 * M, "down_bps": 905e6, "up_bps": 446e6, "bytes": 1}, "history": [],
                      "next": NOW + 280 * M, "error": None},
    }


# --- hardware ---------------------------------------------------------------------------------

def hardware(tick: int, alerts: bool = False) -> dict:
    load = (58 if alerts else 14) + 5 * math.sin(tick / 6)
    cpu_w = 21 + load * 0.62
    wall = (cpu_w / 0.9 + 16.4 + 41.0) / 0.87

    def gpu_load(i):
        if i % 120 < 44:
            return round(2 + 4 * noise(i * 3))
        return round(min(100, (62 + 34 * noise(i * 5)) if (i // 7) % 3 != 2 else 6 + 5 * noise(i)))

    gpu_history = [gpu_load(i) for i in range(tick - 120, tick)]
    return {
        "ok": True, "error": None,
        "inventory": {"board": "B650M Pro RS", "vendor": "ASRock", "bios": "3.20", "bios_date": "2025-03-14",
                      "cpu": {"model": "AMD Ryzen 7 7700", "cores": 8, "threads": 16}, "ram_bytes": 64 * GIB,
                      "disks": [{"name": "nvme0n1", "bytes": 2 * 10**12, "model": "WD_BLACK SN850X 2000GB", "kind": "nvme"},
                                {"name": "sda", "bytes": 8 * 10**12, "model": "ST8000VN004-3CP101", "kind": "hdd"}],
                      "gpus": [{"name": "NVIDIA GeForce RTX 4060", "mem_total": 8 * GIB}]},
        "power": {"cpu_w": cpu_w, "cpu_measured": True, "cpu_load": load, "gpu_w": 16.4, "gpu_limit_w": 115.0, "rest_w": 41.0, "wall_w": wall,
                  "history": {"step": 5.0, "wall": [round(88 + 9 * math.sin(i / 9) + 22 * (1 if i % 47 < 6 else 0) + 4 * noise(i)) for i in range(tick - 120, tick)]},
                  "today": {"wh": 1412.0, "counted_s": 15 * H, "avg_w": 94.1}, "month_kwh": 68.0, "month_cost": 9.52, "price": 0.14, "currency": "$"},
        "gpu": {"cards": [{"name": "NVIDIA GeForce RTX 4060", "load": gpu_history[-1], "mem_used": int(5.9 * GIB), "mem_total": 8 * GIB}],
                "history": {"step": 5.0, "load": gpu_history}, "apps": {"count": 5, "mem": int(5.7 * GIB)}, "error": None},
        "temps": [{"name": "cpu", "c": (63.5 if alerts else 44.6) + math.sin(tick / 5), "warn": 85.0, "crit": 95.0},
                  {"name": "gpu", "c": 38.0, "warn": 80.0, "crit": 90.0},
                  {"name": "nvme0", "c": 72.4 if alerts else 41.9, "warn": 69.85, "crit": 84.85},
                  {"name": "board", "c": 33.0, "warn": 60.0, "crit": 70.0}],
        "fans": [{"name": "cpu", "rpm": 1380 if alerts else 820}, {"name": "case", "rpm": 910 if alerts else 640}, {"name": "gpu", "percent": 0.0}],
        "volts": [{"name": "Vcore", "v": 1.024}, {"name": "+12V", "v": 12.096}, {"name": "+5V", "v": 5.04}, {"name": "+3.3V", "v": 3.312}],
        "board_sensors": True,
        "ups": {"present": True, "model": "APC Back-UPS 1500", "state": "discharging" if alerts else "fully-charged", "on_battery": alerts,
                "percent": 86.0 if alerts else 100.0, "runtime_s": 1920 if alerts else 2700},
        "room": {"configured": True, "c": 23.5},
    }


SCENARIOS = {"demo": False, "alerts": True}

# What the event log shows when the page opens: a quiet day with a few things worth a line.
EVENTS = [
    (13 * H + 20 * M, "SPEED", "info", "918 Mbps down, 451 Mbps up"),
    (11 * H + 2 * M, "CTR", "info", "backup-nightly exited -> running"),
    (10 * H + 49 * M, "CTR", "warn", "backup-nightly running -> exited"),
    (7 * H + 20 * M, "SPEED", "info", "912 Mbps down, 448 Mbps up"),
    (5 * H + 41 * M, "PING", "warn", "internet 1.1.1.1 not answering"),
    (5 * H + 40 * M, "PING", "info", "internet answering again (13 ms)"),
    (3 * H + 12 * M, "CTR", "warn", "grafana removed"),
    (3 * H + 11 * M + 48, "CTR", "info", "grafana appeared (running)"),
    (3 * H + 11 * M + 47, "PORT", "warn", "3000/tcp opened by grafana (*)"),
    (80 * M, "SPEED", "info", "905 Mbps down, 446 Mbps up"),
]

MADE_UP = {(tag, text) for _, tag, _, text in EVENTS}

# --- recording --------------------------------------------------------------------------------

# Put in front of the page's own scripts with ?record=1. Time, timers, animation frames and the
# data stream are all taken over: nothing moves until the recorder calls __record.step(ms).
RECORD_SCRIPT = """<script>
(() => {
  const RealDate = Date;
  const base = %(base)d;
  let now = 0;
  window.Date = class extends RealDate {
    constructor(...args) { if (args.length) super(...args); else super(base + now); }
    static now() { return base + now; }
  };
  performance.now = () => now;
  let frames = [];
  window.requestAnimationFrame = (callback) => { frames.push(callback); return frames.length; };
  window.cancelAnimationFrame = () => {};
  let timers = [];
  let next = 1;
  window.setTimeout = (fn, ms = 0, ...args) => { timers.push({ id: next, at: now + ms, fn, args }); return next++; };
  window.setInterval = (fn, ms = 0, ...args) => { timers.push({ id: next, at: now + ms, every: Math.max(1, ms), fn, args }); return next++; };
  window.clearTimeout = window.clearInterval = (id) => { timers = timers.filter((timer) => timer.id !== id); };
  const listeners = [];
  const snapshots = [];
  let sent = -1;
  window.EventSource = class {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSED = 2;
    constructor() { this.readyState = 1; }
    addEventListener(type, fn) { if (type === "message") listeners.push(fn); }
    set onmessage(fn) { listeners.push(fn); }
    set onerror(fn) {}
    set onopen(fn) {}
    close() {}
  };
  window.__record = {
    async load(scenario, count) {
      for (let tick = 0; tick < count; tick += 1) {
        snapshots.push(await (await fetch(`/demo/snapshot?scenario=${scenario}&tick=${tick}`)).text());
      }
      return snapshots.length;
    },
    step(ms) {
      const until = now + ms;
      for (;;) {
        // One snapshot a second, as the server would send it.
        const second = Math.floor(until / 1000);
        if (sent < second && sent + 1 < snapshots.length) {
          sent += 1;
          now = Math.max(now, sent * 1000);
          for (const fn of listeners) fn({ data: snapshots[sent] });
          continue;
        }
        const due = timers.filter((timer) => timer.at <= until).sort((a, b) => a.at - b.at)[0];
        if (!due) break;
        now = Math.max(now, due.at);
        if (due.every) due.at += due.every;
        else timers = timers.filter((timer) => timer !== due);
        due.fn(...due.args);
      }
      now = until;
      const run = frames;
      frames = [];
      for (const callback of run) callback(now);
      return now;
    },
  };
})();
</script>
<style>
  /* Transitions run on the real clock, which a recording does not follow. */
  *, *::before, *::after { transition: none !important; }
</style>"""


def main(argv: list[str] | None = None) -> None:
    options = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    options.add_argument("--port", type=int, default=8799)
    options.add_argument("--scenario", choices=sorted(SCENARIOS), default="demo")
    settings = options.parse_args(argv)

    # The real app, kept off the network, with a history of its own that is thrown away afterwards.
    state = Path(tempfile.mkdtemp(prefix="rackside-demo-")) / "state.json"
    state.write_text(json.dumps({"events": [{"ts": NOW - ago, "tag": tag, "level": level, "text": text} for ago, tag, level, text in EVENTS]}))
    os.environ.update(DASH_STATE=str(state), DASH_PROBES="0", DASH_SPEEDTEST_HOURS="0", DASH_PORT=str(settings.port))
    sys.path.insert(0, str(ROOT))

    import uvicorn
    from starlette.responses import HTMLResponse, JSONResponse
    from starlette.routing import Route

    from rack_dashboard import app as dash
    from rack_dashboard import paths

    def parts(scenario: str, tick: int) -> tuple[dict, dict, dict]:
        alerts = SCENARIOS[scenario]
        return containers(tick, alerts), network(tick + 240, alerts), hardware(tick + 240, alerts)

    live = {"tick": 0}

    class Part:
        """Stands in for one collector; the containers one moves the clock on."""

        def __init__(self, index: int):
            self.index = index

        def collect(self) -> dict:
            if self.index == 0:
                live["tick"] += 1
            return parts(settings.scenario, live["tick"])[self.index]

        def close(self) -> None:
            pass

    dash.containers, dash.network, dash.hardware = Part(0), Part(1), Part(2)
    dash.socket = SimpleNamespace(gethostname=lambda: "atlas")
    dash.BOOT_TIME = NOW - (12 * 86400 + 7 * H + 14 * M)

    async def page(request):
        html = (paths.FRONTEND / "index.html").read_text()
        if request.query_params.get("record"):
            html = html.replace("<head>", "<head>" + RECORD_SCRIPT % {"base": int(NOW * 1000)}, 1)
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    async def snapshot(request):
        scenario = request.query_params.get("scenario", settings.scenario)
        if scenario not in SCENARIOS:
            return JSONResponse({"detail": f"no scenario {scenario}"}, status_code=404)
        tick = int(request.query_params.get("tick", "0"))
        made = dash.assemble(*parts(scenario, tick), observe=False)
        made["ts"] = NOW + tick
        # Only the made-up events: the one this server logged as it started has today's real time.
        made["events"] = [event for event in made["events"] if (event.get("tag"), event.get("text")) in MADE_UP]
        return JSONResponse(made)

    dash.app.router.routes.insert(0, Route("/demo/snapshot", snapshot))
    dash.app.router.routes.insert(0, Route("/", page))
    print(f"Rackside with made-up data ({settings.scenario}): http://127.0.0.1:{settings.port}")
    uvicorn.run(dash.app, host="127.0.0.1", port=settings.port, log_level="warning")


if __name__ == "__main__":
    main()
