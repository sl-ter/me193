#!/usr/bin/env python3
"""Curses TUI shown automatically on SSH login: IP, CPU, memory, disk,
uptime. Reads only from stdlib/proc, so it needs nothing installed.
Press q to drop into a normal shell, +/- to change the refresh rate."""

import curses
import os
import socket
import time

REFRESH_INTERVAL_S = 2.0


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "unknown"
    finally:
        s.close()


def read_cpu_times():
    with open("/proc/stat") as f:
        fields = [int(x) for x in f.readline().split()[1:]]
    idle = fields[3] + fields[4]
    return idle, sum(fields)


def get_cpu_percent(sample_s):
    idle1, total1 = read_cpu_times()
    time.sleep(sample_s)
    idle2, total2 = read_cpu_times()
    d_idle, d_total = idle2 - idle1, total2 - total1
    if d_total == 0:
        return 0.0
    return 100.0 * (1 - d_idle / d_total)


def get_memory():
    info = {}
    with open("/proc/meminfo") as f:
        for line in f:
            key, value = line.split(":", 1)
            info[key] = int(value.strip().split()[0]) * 1024
    total = info["MemTotal"]
    available = info.get("MemAvailable", info["MemFree"])
    return total - available, total


def get_disk():
    usage = os.statvfs("/")
    total = usage.f_frsize * usage.f_blocks
    free = usage.f_frsize * usage.f_bavail
    return total - free, total


def get_uptime():
    with open("/proc/uptime") as f:
        return float(f.readline().split()[0])


def human_bytes(n):
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024:
            return "{:.1f}{}".format(n, unit)
        n /= 1024
    return "{:.1f}PiB".format(n)


def human_duration(seconds):
    days, seconds = divmod(int(seconds), 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, _ = divmod(seconds, 60)
    parts = []
    if days:
        parts.append("{}d".format(days))
    if hours or days:
        parts.append("{}h".format(hours))
    parts.append("{}m".format(minutes))
    return " ".join(parts)


def safe_line(stdscr, row, text):
    max_y, max_x = stdscr.getmaxyx()
    if 0 <= row < max_y:
        try:
            stdscr.addnstr(row, 0, text, max(0, max_x - 1))
        except curses.error:
            pass


def draw(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    refresh_interval = REFRESH_INTERVAL_S
    hostname = socket.gethostname()

    while True:
        ip = get_ip()
        mem_used, mem_total = get_memory()
        disk_used, disk_total = get_disk()
        uptime_s = get_uptime()
        cpu_pct = get_cpu_percent(min(0.3, refresh_interval))

        stdscr.erase()
        row = 0
        safe_line(stdscr, row, " {} -- Board Dashboard".format(hostname)); row += 1
        safe_line(stdscr, row, "=" * 60); row += 2
        safe_line(stdscr, row, "  IP:            {}".format(ip)); row += 2
        safe_line(stdscr, row, "  CPU:           {:5.1f}%".format(cpu_pct)); row += 1
        safe_line(stdscr, row, "  Memory:        {} / {}".format(human_bytes(mem_used), human_bytes(mem_total))); row += 1
        safe_line(stdscr, row, "  Disk (/):      {} / {}".format(human_bytes(disk_used), human_bytes(disk_total))); row += 1
        safe_line(stdscr, row, "  Uptime:        {}".format(human_duration(uptime_s))); row += 2
        safe_line(stdscr, row, "-" * 60); row += 1
        safe_line(stdscr, row, "  refresh: {:.1f}s   [+/-] adjust   [q] quit to shell".format(refresh_interval))
        stdscr.refresh()

        deadline = time.time() + refresh_interval
        while time.time() < deadline:
            ch = stdscr.getch()
            if ch == ord("q"):
                return
            elif ch == ord("+"):
                refresh_interval = min(10.0, refresh_interval + 0.5)
            elif ch == ord("-"):
                refresh_interval = max(0.5, refresh_interval - 0.5)
            time.sleep(0.05)


def main():
    curses.wrapper(draw)


if __name__ == "__main__":
    main()
