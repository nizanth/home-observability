#!/usr/bin/env bash
# Install the OTel collector agent as a launchd daemon on macOS.
# Usage: sudo ./install.sh <gateway-host:4317>
set -euo pipefail

GATEWAY="${1:?usage: sudo ./install.sh <gateway-host:4317>}"
VERSION="0.116.0"
ARCH="$(uname -m | sed 's/x86_64/amd64/')" # arm64 | amd64
PREFIX=/usr/local/otelcol
LABEL=io.home.otelcol
HERE="$(cd "$(dirname "$0")" && pwd)"

[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }

mkdir -p "$PREFIX"
curl -fsSL "https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v${VERSION}/otelcol-contrib_${VERSION}_darwin_${ARCH}.tar.gz" \
  | tar -xz -C "$PREFIX" otelcol-contrib
cp "$HERE/agent.yaml" "$PREFIX/config.yaml"

# Runs as root so it can read all logs; the ${env:HOME} in agent.yaml is set below.
USER_HOME="$(eval echo "~${SUDO_USER:-root}")"

cat > "/Library/LaunchDaemons/${LABEL}.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>${LABEL}</string>
  <key>ProgramArguments</key><array>
    <string>${PREFIX}/otelcol-contrib</string>
    <string>--config=${PREFIX}/config.yaml</string>
  </array>
  <key>EnvironmentVariables</key><dict>
    <key>GATEWAY_ENDPOINT</key><string>${GATEWAY}</string>
    <key>HOME</key><string>${USER_HOME}</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardErrorPath</key><string>/var/log/otelcol.err.log</string>
</dict></plist>
PLIST

launchctl bootout system "/Library/LaunchDaemons/${LABEL}.plist" 2>/dev/null || true
launchctl bootstrap system "/Library/LaunchDaemons/${LABEL}.plist"
echo "otelcol agent running -> ${GATEWAY}  (logs: /var/log/otelcol.err.log)"
echo "uninstall: sudo launchctl bootout system /Library/LaunchDaemons/${LABEL}.plist && sudo rm -rf ${PREFIX} /Library/LaunchDaemons/${LABEL}.plist"
