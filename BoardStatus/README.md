# Board Status — 10/1

A second Arduino App Lab app for the UNO Q, alongside `ArduinoDisplay/` but
deliberately separate from it (not sharing code, and only one app owns the
LED matrix at a time — this one is meant to be started when you want to
check on the board, not left running constantly). It solves a different
problem: once you're done walking across rooms/networks with the board,
how do you know its IP to SSH in, and what's happening on the board once
you're in?

Two independent pieces:

1. **LED matrix app** (`app.yaml` / `python/main.py` / `sketch/`) — scrolls
   the board's real IP address, then CPU/memory/disk percent, then uptime.
   Run it from App Lab like any other app.
2. **SSH dashboard** (`board_dashboard.py`, `ssh_login_hook.sh`,
   `update_ip.sh`) — a curses TUI that shows the same metrics the moment
   you SSH into the board, independent of which App Lab app (if any) is
   running. Lives entirely on the board's Linux host, outside Docker.

## Why there's an `update_ip.sh` at all

Each App Lab app runs in its own Docker container on an isolated bridge
network (confirmed via `docker inspect`) — it can't see the board's real
wifi IP, only a Docker-internal one. But each app's folder on the host
(`/home/arduino/ArduinoApps/board-status`) is bind-mounted straight into
its container as `/app`, so a plain file written into this folder is
readable from inside the sandboxed app. `update_ip.sh` writes the real IP
to `ip_address.txt` here; `python/main.py` just reads it back out.
`board_dashboard.py` doesn't need this trick — it runs directly on the
host, not in a container, so it can read the real IP itself.

## Install (one-time, run on the board over SSH)

```bash
# Let the IP-writer run every minute (no sudo needed — it's your own crontab)
chmod +x ~/ArduinoApps/board-status/update_ip.sh
(crontab -l 2>/dev/null; echo "* * * * * /home/arduino/ArduinoApps/board-status/update_ip.sh") | crontab -

# Auto-show the dashboard on interactive SSH logins
chmod +x ~/ArduinoApps/board-status/board_dashboard.py
echo '. /home/arduino/ArduinoApps/board-status/ssh_login_hook.sh' >> ~/.bashrc
```

Then start "Board Status" from App Lab when you actually want the LED
matrix readout — it'll briefly take over the matrix from whatever app was
running (confirmed fine with Sam; `ArduinoDisplay` isn't touched otherwise).

## Uninstall

```bash
crontab -l | grep -v update_board_ip | crontab -   # drop the cron line
# remove the ". .../ssh_login_hook.sh" line from ~/.bashrc by hand
```

## Verified

- `update_ip.sh` correctly picks the real wifi IP (not a Docker bridge IP)
  via `ip route get`'s `src` field — tested on the `tufts_eecs` network.
- `board_dashboard.py` was not yet confirmed to actually auto-launch on a
  live SSH session (the `.bashrc` hook install was done via `board_exec`,
  not tested end-to-end by actually SSHing in after it) — **worth
  double-checking next session.**
