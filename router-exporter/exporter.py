"""Prometheus exporter for home routers. Currently supports Netgear Orbi via its local SOAP API
(pynetgear); to support another router, replace poll() with that router's API calls.

Polls on a fixed interval (the router is slow and shouldn't be hit per-scrape)
and exposes WAN traffic totals, router load, mesh satellites and attached devices.
"""
import logging
import os
import time
from datetime import timedelta

from prometheus_client import Gauge, start_http_server
from pynetgear import Netgear

HOST = os.environ.get("ROUTER_HOST", "192.168.1.1")
PORT = int(os.environ.get("ROUTER_PORT", "443"))
SSL = os.environ.get("ROUTER_SSL", "true").lower() == "true"
USER = os.environ.get("ROUTER_USER", "admin")
PASSWORD = os.environ.get("ROUTER_PASSWORD", "")
INTERVAL = int(os.environ.get("ROUTER_INTERVAL", "60"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("router-exporter")

UP = Gauge("router_up", "1 if the last poll of the router succeeded")
METER_ENABLED = Gauge("router_traffic_meter_enabled", "1 if the router's Traffic Meter is enabled (needed for traffic metrics)")
TRAFFIC = Gauge("router_wan_traffic_megabytes", "WAN traffic total from the router's Traffic Meter", ["period", "direction"])
DEVICES = Gauge("router_connected_devices", "Attached devices", ["connection_type", "ssid"])
DEVICE_UP = Gauge("router_device_connected", "Attached device (1 per device)", ["name", "ip", "mac", "connection_type", "ap_mac"])
DEVICE_RATE = Gauge("router_device_link_rate_mbps", "Device link rate", ["name", "mac"])
DEVICE_SIGNAL = Gauge("router_device_signal_percent", "Device WiFi signal strength", ["name", "mac"])
SATELLITES = Gauge("router_satellite_info", "Connected mesh satellites (1 per satellite)", ["name", "ip", "mac", "model"])

PERIODS = {"Today": "today", "Yesterday": "yesterday", "Week": "week", "Month": "month", "LastMonth": "last_month"}


def mb(value):
    # Week/month values come back as (total, daily avg)
    if isinstance(value, tuple):
        return value[0]
    if isinstance(value, (int, float)):
        return value
    return None


def poll(router):
    # Used only as a liveness check: on some firmware versions GetSystemInfo
    # returns static placeholders (CPU 100%, 256MB RAM), so it isn't exported.
    if router.get_system_info() is None:
        raise RuntimeError("no response from router (bad password or SOAP API disabled?)")

    enabled = router.get_traffic_meter_enabled()
    METER_ENABLED.set(1 if enabled else 0)
    meter = router.get_traffic_meter() or {}
    TRAFFIC.clear()
    for key, period in PERIODS.items():
        for direction in ("Upload", "Download"):
            v = mb(meter.get(f"New{key}{direction}"))
            if v is not None:
                TRAFFIC.labels(period, direction.lower()).set(v)

    devices = router.get_attached_devices_2() or router.get_attached_devices() or []
    DEVICES.clear(); DEVICE_UP.clear(); DEVICE_RATE.clear(); DEVICE_SIGNAL.clear()
    counts = {}
    for d in devices:
        ctype = d.type or "unknown"
        ssid = getattr(d, "ssid", None) or ""
        counts[(ctype, ssid)] = counts.get((ctype, ssid), 0) + 1
        name = d.name or d.mac
        DEVICE_UP.labels(name, d.ip or "", d.mac, ctype, getattr(d, "conn_ap_mac", None) or "").set(1)
        if d.link_rate not in (None, ""):
            try:
                DEVICE_RATE.labels(name, d.mac).set(float(d.link_rate))
            except ValueError:
                pass
        if d.signal is not None:
            DEVICE_SIGNAL.labels(name, d.mac).set(d.signal)
    for (ctype, ssid), n in counts.items():
        DEVICES.labels(ctype, ssid).set(n)

    SATELLITES.clear()
    for s in router.get_satellites() or []:
        SATELLITES.labels(*(s.get(k) or "" for k in ("DeviceName", "IP", "MAC", "ModelName"))).set(1)

    return len(devices)


def main():
    if not PASSWORD:
        log.error("ROUTER_PASSWORD is not set; exporting router_up=0 only")
    start_http_server(9100)
    router = Netgear(password=PASSWORD, host=HOST, user=USER, port=PORT, ssl=SSL)
    logged_in = False
    while True:
        try:
            if PASSWORD:
                if not logged_in:
                    logged_in = router.login_try_port()
                    if not logged_in:
                        raise RuntimeError("login failed")
                n = poll(router)
                UP.set(1)
                log.info("polled %s: %d devices", HOST, n)
            else:
                UP.set(0)
        except Exception as e:  # keep exporting; router hiccups are common
            UP.set(0)
            logged_in = False
            log.warning("poll failed: %s", e)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
