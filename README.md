# Home observability stack

```
 apps (OTLP SDKs, Traefik/Caddy) ─┐
 docker container logs ───────────┤
 host + container metrics ────────┼─► OpenTelemetry Collector ─┬─► Loki       (logs,    30d)
 http uptime probes ──────────────┤                            ├─► Tempo      (traces,   7d)
 AdGuard / Jellyfin exporters ────┘                            └─► Prometheus (metrics, 30d)
                                                                        │
                                                          Grafana: dashboards + alert rules ─► Telegram
```

## Run
```
cp .env.example .env   # fill in passwords, AdGuard/router creds, Telegram bot
docker compose up -d
open http://localhost:3000   # Home > Home Overview
```

The top of Home Overview is a status page: overall health, counts, firing alerts, a table of every service (hosts, containers, websites, Postgres, router/DNS, exporters) with UP/DOWN and how long it has been down, and the apps sending traces. Status comes from the `home:service:*` rules in `prometheus/rules/home-status.yml`; a service that has been down for over a day drops off the table.

**Home > Traces** is for following requests end to end: a service map (from the collector's `servicegraph` connector), rate / error / p95 charts whose dots are example traces (exemplars), tables of recent, slow and failed traces, and a trace view plus matching logs for the trace you click.

## Add a service
- **Uptime**: add an endpoint under `httpcheck.targets` in `otel/collector.yaml`; it appears on the dashboard and is covered by the *Site down* alert automatically.
- **Metrics**: add a scrape job under the `prometheus` receiver.
- **Logs**: containers are picked up automatically. For readable service names instead of container IDs, add to `/etc/docker/daemon.json` and restart docker (applies to newly created containers):
  ```json
  { "log-driver": "json-file", "log-opts": { "labels-regex": "^com\\.docker\\.compose\\.(service|project)$" } }
  ```
- **Traces**: apps you write: set `OTEL_EXPORTER_OTLP_ENDPOINT=http://<host>:4317` and `OTEL_SERVICE_NAME`. Traefik (`tracing.otlp`) and Caddy can emit a trace per request, which is the practical way to trace off-the-shelf sites like Jellyfin.

## Per-app notes
- **AdGuard Home**: `adguard-exporter` gives query, block and latency metrics.
- **Jellyfin**: enable metrics in the admin dashboard (check `http://<host>:8096/metrics`). Jellyfin has no native OTel, so logs come from its container and uptime from `/health`.

## Alerts (Grafana, provisioned in `grafana/provisioning/alerting/alerts.yaml`)
Site down (2 min), disk > 90%, container memory > 90%. Missing data on *Site down* also fires, so a dead collector isn't silent. Alerts are sent to a Telegram bot (`TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` in `.env`).

## Anomaly detection
Prometheus learns a normal band for each tagged signal (the adaptive strategy from
[grafana/promql-anomaly-detection](https://github.com/grafana/promql-anomaly-detection),
vendored in `prometheus/rules/anomaly-adaptive.yml`): a 1h mean ± 2σ, smoothed over 26h,
plus the same hour yesterday and last week, so routine daily/weekly patterns aren't flagged.

- **What's watched**: `prometheus/rules/anomaly-home.yml` covers host, containers, probes,
  logs, Postgres, DNS, WiFi, WAN and (once apps send traces) service RED metrics. To add a
  signal, add a recording rule with `anomaly_name`, `anomaly_type`
  (`resource` | `requests` | `latency` | `errors`) and a `subject` label.
- **Alerts**: *Anomaly detected* fires after 15 min outside the band and goes to Telegram,
  one message per signal type, repeating every 12h. A series must have existed for a day
  before it alerts, so new containers/devices get a learning period.
- **Dashboard**: Home > Anomalies shows what's anomalous now and each signal against its band.
- Values that are normally zero (e.g. errors) aren't learned; use threshold alerts for those.


- Host/log collection needs a Linux Docker host. On macOS Docker Desktop, the `/hostfs` and docker log paths won't reflect the real machine.
- Multiple machines: copy `agent/` to the other machine and run `CENTRAL_HOST=<this host's IP> HOST_NAME=$(hostname) docker compose up -d`. It ships that machine's host/container metrics and container logs here, labelled with its `host_name`, and accepts OTLP from local apps on its own 4317/4318.
- Ports 4317/4318 have no auth; keep them LAN-only.

## White paper
[docs/whitepaper.md](docs/whitepaper.md) explains the design: architecture, agents, anomaly detection, security trade-offs and configuration examples.

## License
Apache License 2.0, see [LICENSE](LICENSE). `prometheus/rules/anomaly-adaptive.yml` is vendored from
[grafana/promql-anomaly-detection](https://github.com/grafana/promql-anomaly-detection) (Apache-2.0, Copyright Grafana Labs).
