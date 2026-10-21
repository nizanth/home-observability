# Home Tracing: Self-Hosted Observability for a Home Lab

*Metrics, logs, traces and anomaly alerts for a home network, and why rising bot traffic makes them matter.*

Full white paper with every config file: [nizanth.github.io/home-observability](https://nizanth.github.io/home-observability/) · Code: [github.com/nizanth/home-observability](https://github.com/nizanth/home-observability) (Apache-2.0)

## The problem

A modern home network runs as many services as a small office, but with none of the tooling. Mine mixes a Linux server, a Mac running containers, a Windows PC, a media server, a DNS filter, a mesh Wi-Fi router and a local AI model. When something breaks, the owner usually finds out from a family member.

Commercial monitoring products are priced and sized for companies, and most send data to a third-party cloud. Home Tracing aims for three things instead:

- **One pane of glass**: every host, container, website and network device on a single status page.
- **Private by default**: telemetry is stored on a machine at home.
- **Low effort**: new containers and log files are discovered automatically, and most signals need no hand-tuned alert thresholds.

## Why watch home traffic at all

Bots now generate most web traffic. Imperva's [2025 Bad Bot Report](https://www.imperva.com/resources/resource-library/reports/2025-bad-bot-report/) puts automated traffic at 51% of all web traffic, and bad bots at 37%. The report links the growth to AI tools that make bots easier to build.

A home network is a target in two directions:

- **Inbound**: any self-hosted site or app reachable from the internet is scanned and scraped.
- **Outbound**: compromised home devices are rented out as proxies. The FBI's [June 2025 warning on BADBOX 2.0](https://www.ic3.gov/PSA/2025/PSA250605) describes millions of infected streaming boxes, projectors and picture frames used this way. One sign of infection it lists is "unexplained or suspicious Internet traffic".

You rarely notice either, because nothing breaks. Learned anomaly bands turn those quiet changes into a phone notification. Here is what the stack watches and what a change can mean:

- **One device suddenly makes far more DNS queries** (DNS queries per client): malware, a device recruited as a proxy, or a misbehaving app.
- **The share of blocked DNS queries jumps** (DNS block ratio): a device contacting tracking, ad or malicious domains.
- **Upload or download moves outside its usual hours or volume** (WAN throughput): proxy or botnet use, or an unexpected backup.
- **New devices join the network** (connected Wi-Fi devices): an unknown device, or a guest.
- **Requests to a self-hosted app spike** (request rate and log volume): scanning or scraping bots.
- **Network errors or drops rise on a host** (host network errors): a flood, a failing link or a bad cable.

These alerts point at where to look; they do not prove a bot. Telling bots from people needs request detail, such as user agents and paths in reverse-proxy logs, which the stack also keeps.

## How it fits together

![Every machine reports to one OpenTelemetry Collector, which feeds Prometheus, Loki and Tempo; Grafana reads all three and sends alerts to Telegram.](architecture.png)

All telemetry flows through one OpenTelemetry Collector, which sends each kind of data to a store built for it:

- **Metrics → Prometheus**, kept 30 days.
- **Logs → Loki**, kept 30 days.
- **Traces → Tempo**, kept 7 days.

Grafana sits on top with dashboards and alert rules. The collector also runs website uptime checks, builds a service map from traces, and scrapes small exporters for the DNS filter, the router and the host's network counters.

Each machine runs one lightweight agent:

- **Linux**: a Docker container collecting host and container metrics and container logs.
- **macOS**: a native background service for host metrics and app logs, plus a container agent inside the Docker VM for container stats and logs.
- **Windows**: a Windows service collecting host metrics, the Windows Event Log and app logs.

## Three dashboards

- **Home Overview** answers *"is everything up right now?"*: overall health, firing alerts, and a table of every host, container, website, database, router and DNS service with how long it has been down.
- **Traces** answers *"why was this request slow or failing?"*: a service map, rate, error and latency charts whose dots link to example requests, and the matching logs.
- **Anomalies** answers *"what is behaving unusually?"*: each signal plotted against its learned normal band.

## Alerts that learn what normal looks like

Clear failures get fixed thresholds. Everything else gets a learned band. All alerts go to a private Telegram bot, which works on any phone without opening a port to the internet.

The fixed alerts:

- **Site down**: a website gives no successful answer for 2 minutes, or the checks themselves stop arriving, so a dead collector can't fail silently.
- **Disk almost full**: over 90% for 10 minutes.
- **Container memory high**: over 90% of its limit for 10 minutes.
- **Container down**: a container that normally runs has been stopped for 2 minutes.

The learned alerts use the adaptive method from Grafana's open-source [promql-anomaly-detection](https://github.com/grafana/promql-anomaly-detection) project. Each signal's normal band is the widest of three estimates:

- **Short term**: the last hour's average, give or take two standard deviations.
- **Margin**: the last hour's average, give or take 50%.
- **Long term**: the same hour one day and one week earlier.

The long-term band is what stops a nightly backup or a weekend movie night from raising an alert. A new signal has to exist for a day before it can alert, and the weekly comparison kicks in after a week.

Adding a signal is one Prometheus rule with three labels:

```yaml
- record: anomaly:input:host_cpu
  expr: >-
    label_join(100 * (1 - avg by (host_name) (system_cpu_utilization{state="idle"})),
               "subject", " ", "host_name")
  labels:
    anomaly_name: host_cpu
    anomaly_type: resource      # resource | requests | latency | errors
    anomaly_strategy: adaptive
```

A resulting Telegram message looks like this:

```text
Firing: Anomaly detected
host_cpu · server-1 is above its normal range (now 87.4)
Dashboard: Home > Anomalies (anomaly_name=host_cpu)
```

## Setting up Telegram alerts

1. In Telegram, message @BotFather, send `/newbot` and copy the token.
2. Send any message to your new bot.
3. Find your chat ID:

```bash
curl -s "https://api.telegram.org/bot<token>/getUpdates" | grep -o '"chat":{"id":[-0-9]*'
```

4. Put the token and chat ID in the `.env` file. Grafana picks them up as a provisioned contact point.

## Local AI

I also run models locally with LM Studio, so prompts and answers stay at home. Today the stack checks that LM Studio's API is answering, and watches the CPU, memory and load of the machine running it. Long inference runs show up as sustained load, which is why learned bands work better here than fixed limits.

Next steps I'm considering:

- **Trace the apps that call the model**, recording latency, model name and token counts, using OpenTelemetry's [GenAI conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/).
- **Alert when model responses slow down**, for example when a model falls back to the CPU.
- **Have the local model summarize each alert** in plain language before it goes to Telegram.

## Security trade-offs

The stack assumes a trusted home network, so a few rules matter:

- **Keep the ports local.** The collector's ports (4317, 4318) and Grafana (3000) must never be forwarded through the router. Docker-published ports bypass host firewalls like ufw, so bind them to the LAN address instead.
- **Separate untrusted devices.** Put IoT and guest devices on their own network.
- **Know what leaves home.** Alert text goes to Telegram and names hosts and URLs. Grafana, Loki and Tempo also send anonymous usage statistics by default; each has a setting to turn this off.
- **Treat dashboards as private.** Device inventory shows device names, IPs and MAC addresses.

## Try it

```bash
git clone https://github.com/nizanth/home-observability.git
cd home-observability
cp .env.example .env   # set a host name, passwords and the Telegram bot
docker compose up -d
```

Then open Grafana on port 3000 and install one agent on each other machine. The [full white paper](https://nizanth.github.io/home-observability/) has the per-platform install commands, every config file and the known limitations.

## What's next

- Encrypted, authenticated transport between agents and the collector.
- A host-down alert, and a heartbeat from outside the network.
- Measuring the stack's own footprint (RAM, CPU and disk per day).

Feedback and pull requests are welcome on [GitHub](https://github.com/nizanth/home-observability).
