# Board Status — 10/1

A second Arduino App Lab app for the UNO Q, alongside `ArduinoDisplay/` but
deliberately separate from it (not sharing code, and only one app owns the
LED matrix at a time — this one takes it over briefly on boot/when started,
not left fighting `ArduinoDisplay` for it). It solves a different problem:
how do you know the board's IP to SSH in, and what's happening on the
board once you're in?

Two independent pieces:

1. **LED matrix app** (`app.yaml` / `python/main.py` / `sketch/`) — scrolls
   the board's real IP address on loop, nothing else. Starts automatically
   on boot (see Autostart below) so it's showing before you'd even think
   to look for a computer to run App Lab from.
2. **SSH dashboard** (`board_dashboard.py`, `ssh_login_hook.sh`) — a curses
   TUI that pops up the moment you SSH into the board: a big block-digit
   IP banner, color-coded CPU/memory/disk bars with a CPU sparkline
   history, network throughput per interface, and a mini top-5-processes
   list. Independent of which App Lab app (if any) is running — it lives
   entirely on the board's Linux host, outside Docker. Press `q` to drop
   to a normal shell (or run `board_dashboard` any time to reopen it).

## Why there's an `update_ip.sh` at all

Each App Lab app runs in its own Docker container on an isolated bridge
network (confirmed via `docker inspect`) — it can't see the board's real
wifi IP, only a Docker-internal one. But each app's folder on the host
(`/home/arduino/ArduinoApps/board-status`) is bind-mounted straight into
its container as `/app`, so a plain file written into this folder is
readable from inside the sandboxed app. `update_ip.sh` writes the real IP
to `ip_address.txt` here (via a once-a-minute cron job, no sudo needed —
it's the user's own crontab); `python/main.py` just reads it back out.
`board_dashboard.py` doesn't need this trick — it runs directly on the
host, not in a container, so it reads the real IP itself.

## Install (one-time, run on the board over SSH)

```bash
# Let the IP-writer run every minute
chmod +x ~/ArduinoApps/board-status/update_ip.sh
(crontab -l 2>/dev/null; echo "* * * * * /home/arduino/ArduinoApps/board-status/update_ip.sh") | crontab -

# Auto-show the dashboard on interactive SSH logins
chmod +x ~/ArduinoApps/board-status/board_dashboard.py
echo '. /home/arduino/ArduinoApps/board-status/ssh_login_hook.sh' >> ~/.bashrc
```

### Autostart on boot

`arduino-app-cli` (the local CLI App Lab's own UI talks to, backed by the
always-running `arduino-app-cli.service`) can start an app by id directly —
`arduino-app-cli app restart user:board-status` — so a plain systemd unit
hooked to that service is enough to make the matrix app come up with zero
manual steps on every boot, battery-powered or not. This needs real `sudo`
(see **Sudo password** below), so run it yourself over SSH:

```bash
sudo tee /etc/systemd/system/board-status-autostart.service > /dev/null <<'EOF'
[Unit]
Description=Auto-start Board Status app on boot
After=arduino-app-cli.service docker.service
Requires=arduino-app-cli.service docker.service

[Service]
Type=oneshot
User=arduino
Environment=HOME=/home/arduino
ExecStart=/usr/bin/arduino-app-cli app restart user:board-status
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now board-status-autostart.service
```

Two gotchas hit (and fixed) getting this working, worth knowing if it ever
needs touching again:
- Without `User=arduino` + `Environment=HOME=/home/arduino`, systemd runs
  the unit as root with no `$HOME` set at all, and `arduino-app-cli` fails
  outright with `invalid config: $HOME is not defined`.
- Using `app start` instead of `app restart` fails with `App ... Is Running`
  if the app happens to already be up when the unit fires (e.g. you started
  it manually, then the unit reruns) — `restart` handles both "not running"
  and "already running" cleanly.

## Sudo password

`sudo` on `arduino` needs a real password now — nobody knew it for a while
(the guessed default `Arduino` was wrong), which blocked installing tmux,
editing `sshd_config`, and this autostart unit. Unblocked via
`/usr/local/bin/arduino-passwd`, a NOPASSWD-sudo helper built into the
board image specifically for this (`sudo arduino-passwd`, then type a new
password at the hidden prompt — it doesn't print anything, that's normal).
To change it again later, either re-run that, or the standard `passwd` works
fine too now that a real password exists.

**Security note:** having an SSH key installed does *not* disable password
login — `PasswordAuthentication` is still at the Debian default (enabled),
confirmed via `/etc/ssh/sshd_config` with no override in `sshd_config.d/`.
Locking it to key-only needs an explicit `PasswordAuthentication no` edit
plus an sshd restart — not done yet.

## Uninstall

```bash
crontab -l | grep -v update_board_ip | crontab -   # drop the cron line
# remove the ". .../ssh_login_hook.sh" line from ~/.bashrc by hand
sudo systemctl disable --now board-status-autostart.service
sudo rm /etc/systemd/system/board-status-autostart.service
```

## Verified

- `update_ip.sh` correctly picks the real wifi IP (not a Docker bridge IP)
  via `ip route get`'s `src` field — tested across three different
  networks (`XFSETUP-9084`, an iPhone hotspot, `tufts_eecs`).
- `board_dashboard.py` confirmed auto-launching live over a real SSH
  session. Hit one real bug along the way: kitty terminal's default
  `TERM=xterm-kitty` isn't in this board's terminfo database, which made
  `curses.initscr()` raise and (combined with a since-fixed hook bug) once
  left the SSH session dead instead of dropping back to a shell. Fixed by
  catching that specific failure and retrying once under
  `TERM=xterm-256color`.
- `board-status-autostart.service` confirmed `active (exited)`, exit
  status 0, with the app actually restarting end-to-end (sketch
  recompiled/flashed, container recreated) — not just "looks fine on
  paper."
