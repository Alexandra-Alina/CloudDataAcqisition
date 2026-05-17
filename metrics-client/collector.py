"""
metrics-client/collector.py
Local system metrics collector — POSTs timeseries data to the FastAPI backend.

Usage:
    python collector.py [--config config.yaml]

Collected metrics:
    - cpu_load_percent
    - memory_load_percent / memory_used_mb
    - network_in_bytes / network_out_bytes (per-interval deltas)
    - latency_ms (ICMP ping, falls back to TCP connect)
    - power_consumption_w (Intel RAPL via /sys, or None if unavailable)
"""

import argparse
import logging
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import psutil
import requests
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Config ────────────────────────────────────────────────────────────────────

def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ── Metric collectors ─────────────────────────────────────────────────────────

def collect_cpu() -> float:
    return psutil.cpu_percent(interval=1)


def collect_memory() -> tuple[float, float]:
    mem = psutil.virtual_memory()
    return mem.percent, round(mem.used / 1024 ** 2, 2)


def collect_network(iface: str, prev_counters: Optional[dict]) -> tuple[int, int, dict]:
    """Return (bytes_in_delta, bytes_out_delta, current_counters)."""
    all_counters = psutil.net_io_counters(pernic=bool(iface))

    if iface:
        counters = all_counters.get(iface)
        if counters is None:
            available = list(all_counters.keys())
            log.warning("Interface '%s' not found. Available: %s", iface, available)
            counters = psutil.net_io_counters()
    else:
        counters = psutil.net_io_counters()

    current = {"recv": counters.bytes_recv, "sent": counters.bytes_sent}

    if prev_counters is None:
        return 0, 0, current

    delta_in = max(0, current["recv"] - prev_counters["recv"])
    delta_out = max(0, current["sent"] - prev_counters["sent"])
    return delta_in, delta_out, current


def measure_latency_ms(target: str) -> Optional[float]:
    """Measure round-trip latency via ping. Falls back to TCP connect."""
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "2", target],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "time=" in line:
                    time_part = line.split("time=")[-1].split()[0]
                    return round(float(time_part), 3)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Fallback: TCP connect time
    try:
        start = time.monotonic()
        with socket.create_connection((target, 53), timeout=2):
            pass
        return round((time.monotonic() - start) * 1000, 3)
    except OSError:
        return None


# Intel RAPL energy file (Linux only)
_RAPL_ENERGY_FILE = Path("/sys/class/powercap/intel-rapl:0/energy_uj")
_prev_rapl_energy: Optional[float] = None
_prev_rapl_time: Optional[float] = None


def measure_power_w() -> Optional[float]:
    """Read power consumption via Intel RAPL (Linux). Returns None if unavailable."""
    global _prev_rapl_energy, _prev_rapl_time

    if not _RAPL_ENERGY_FILE.exists():
        return None

    try:
        energy_uj = float(_RAPL_ENERGY_FILE.read_text().strip())
        now = time.monotonic()

        if _prev_rapl_energy is not None and _prev_rapl_time is not None:
            delta_uj = energy_uj - _prev_rapl_energy
            # Handle counter wrap-around (max energy from max_energy_range_uj)
            if delta_uj < 0:
                max_file = _RAPL_ENERGY_FILE.parent / "max_energy_range_uj"
                if max_file.exists():
                    max_uj = float(max_file.read_text().strip())
                    delta_uj += max_uj
                else:
                    delta_uj = 0.0

            delta_s = now - _prev_rapl_time
            watts = (delta_uj / 1_000_000) / delta_s if delta_s > 0 else 0.0
            _prev_rapl_energy = energy_uj
            _prev_rapl_time = now
            return round(watts, 2)

        _prev_rapl_energy = energy_uj
        _prev_rapl_time = now
        return None

    except (OSError, ValueError):
        return None


# ── HTTP sender ───────────────────────────────────────────────────────────────

def send_metrics(backend_url: str, api_key: str, payload: dict, timeout: int = 10) -> bool:
    url = f"{backend_url.rstrip('/')}/metrics"
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            timeout=timeout,
        )
        if resp.status_code == 200:
            log.info("Sent OK | cpu=%.1f%% mem=%.1f%% lat=%sms",
                     payload["metrics"].get("cpu_load_percent", 0),
                     payload["metrics"].get("memory_load_percent", 0),
                     payload["metrics"].get("latency_ms", "?"))
            return True
        else:
            log.warning("Backend returned %d: %s", resp.status_code, resp.text[:200])
            return False
    except requests.exceptions.ConnectionError:
        log.error("Cannot connect to backend at %s", url)
        return False
    except requests.exceptions.Timeout:
        log.error("Request timed out after %ds", timeout)
        return False


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Metrics collector")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    args = parser.parse_args()

    config_path = args.config
    if not Path(config_path).exists():
        log.error("Config file not found: %s", config_path)
        sys.exit(1)

    cfg = load_config(config_path)

    host_id = cfg.get("host_id", socket.gethostname())
    backend_url = cfg["backend_url"]
    api_key = cfg["api_key"]
    interval = int(cfg.get("interval_seconds", 30))
    ping_target = cfg.get("ping_target", "8.8.8.8")
    iface = cfg.get("network_interface", "")

    log.info("Starting collector: host=%s interval=%ds backend=%s", host_id, interval, backend_url)

    prev_net = None

    while True:
        loop_start = time.monotonic()

        cpu = collect_cpu()
        mem_pct, mem_mb = collect_memory()
        net_in, net_out, prev_net = collect_network(iface, prev_net)
        latency = measure_latency_ms(ping_target)
        power = measure_power_w()

        payload = {
            "host_id": host_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "cpu_load_percent": cpu,
                "memory_load_percent": mem_pct,
                "memory_used_mb": mem_mb,
                "network_in_bytes": net_in,
                "network_out_bytes": net_out,
                "latency_ms": latency,
                "power_consumption_w": power,
            },
        }

        send_metrics(backend_url, api_key, payload)

        elapsed = time.monotonic() - loop_start
        sleep_time = max(0.0, interval - elapsed)
        time.sleep(sleep_time)


if __name__ == "__main__":
    main()
