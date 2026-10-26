#!/bin/sh
# Writes the board's real wifi/ethernet IP into this app's own folder, which
# is bind-mounted straight into its container as /app — the app's container
# is network-isolated and can't see this IP directly, so main.py just reads
# ip_address.txt back out instead. Installed as a once-a-minute cron job
# (see README.md) since it doesn't need root and cron is already running.
set -eu
OUT="$(dirname "$0")/ip_address.txt"

ip route get 1.1.1.1 2>/dev/null | {
  read -r LINE
  IP=""
  PREV=""
  for TOK in $LINE; do
    if [ "$PREV" = "src" ]; then IP=$TOK; fi
    PREV=$TOK
  done
  if [ -n "$IP" ]; then printf '%s' "$IP" > "$OUT.tmp"; fi
}

if [ -f "$OUT.tmp" ]; then mv "$OUT.tmp" "$OUT"; fi
