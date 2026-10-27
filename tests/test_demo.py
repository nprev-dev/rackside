"""The made-up data behind tools/demo.py and the pictures in the readme."""

from __future__ import annotations

import importlib.util
import ipaddress
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("demo", ROOT / "tools" / "demo.py")
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)

# Where made-up addresses may come from: this machine itself, private networks, the ranges set aside for documentation,
# and the one public address everybody knows.
ALLOWED = [ipaddress.ip_network(net) for net in ("127.0.0.0/8", "192.168.1.0/24", "100.64.0.0/10", "198.51.100.0/24", "203.0.113.0/24", "1.1.1.1/32")]


@pytest.mark.parametrize("scenario", sorted(demo.SCENARIOS))
@pytest.mark.parametrize("tick", [0, 1, 37, 500])
def test_every_scenario_makes_complete_data(scenario, tick):
    alerts = demo.SCENARIOS[scenario]
    containers, network, hardware = demo.containers(tick, alerts), demo.network(tick + 240, alerts), demo.hardware(tick + 240, alerts)

    assert containers["total"] == len(containers["items"]) == sum(containers["states"].values())
    assert len(network["history"]["rx"]) == len(network["history"]["tx"]) == 240
    assert all(len(ping["history"]) == 120 for ping in network["ping"])
    assert len(hardware["gpu"]["history"]["load"]) == 120
    json.dumps([containers, network, hardware], allow_nan=False)


def test_alerts_show_trouble_and_the_demo_does_not():
    calm, alarmed = demo.hardware(300, False), demo.hardware(300, True)

    assert not calm["ups"]["on_battery"] and alarmed["ups"]["on_battery"]
    assert any(item["health"] == "unhealthy" for item in demo.containers(0, True)["items"])
    assert not any(item["health"] == "unhealthy" for item in demo.containers(0, False)["items"])


def test_nothing_in_it_is_a_real_machine():
    text = (ROOT / "tools" / "demo.py").read_text()
    for found in re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text):
        address = ipaddress.ip_address(found)
        assert any(address in net for net in ALLOWED), f"{found} is not a made-up address"
    # A MAC address made up by hand has the "locally administered" bit set, as 02:... does.
    for mac in re.findall(r"\b[0-9a-f]{2}(?::[0-9a-f]{2}){5}\b", text):
        assert int(mac[:2], 16) & 0b10, f"{mac} could be a real network card"
