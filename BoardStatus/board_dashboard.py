#!/usr/bin/env python3
"""Curses TUI shown automatically on SSH login: a big block-digit IP
banner, color-coded CPU/memory/disk meters with sparkline history, network
throughput, and a small top-processes-by-CPU list. Reads only from
stdlib/proc, so it needs nothing installed. Press q to drop into a normal
shell, +/- to change the refresh rate."""

import curses
import locale
import os
import socket
import time
from collections import deque

locale.setlocale(locale.LC_ALL, "")

REFRESH_INTERVAL_S = 2.0
HISTORY_LEN = 40
TOP_PROCESS_COUNT = 5
CLK_TCK = os.sysconf("SC_CLK_TCK")

SPARK_BLOCKS = " ▁▂▃▄▅▆▇█"

BIG_DIGITS = {
    "0": (" _ ", "| |", "|_|"),
    "1": ("   ", "  |", "  |"),
    "2": (" _ ", " _|", "|_ "),
    "3": (" _ ", " _|", " _|"),
    "4": ("   ", "|_|", "  |"),
    "5": (" _ ", "|_ ", " _|"),
    "6": (" _ ", "|_ ", "|_|"),
    "7": (" _ ", "  |", "  |"),
    "8": (" _ ", "|_|", "|_|"),
    "9": (" _ ", "|_|", " _|"),
    ".": ("   ", "   ", " . "),
}

# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------


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


def cpu_percent_from(before, after):
    idle1, total1 = before
    idle2, total2 = after
    d_idle, d_total = idle2 - idle1, total2 - total1
    if d_total <= 0:
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


def read_net_bytes():
    result = {}
    with open("/proc/net/dev") as f:
        lines = f.readlines()[2:]
    for line in lines:
        if ":" not in line:
            continue
        iface, rest = line.split(":", 1)
        iface = iface.strip()
        if iface == "lo" or iface.startswith(("docker", "br-", "veth")):
            continue
        fields = rest.split()
        result[iface] = (int(fields[0]), int(fields[8]))  # rx_bytes, tx_bytes
    return result


def read_proc_cpu_times():
    result = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open("/proc/{}/stat".format(entry)) as f:
                content = f.read()
            rparen = content.rfind(")")
            name = content[content.index("(") + 1:rparen]
            fields = content[rparen + 2:].split()
            utime, stime = int(fields[11]), int(fields[12])
            result[entry] = (name, utime + stime)
        except (OSError, ValueError, IndexError):
            continue
    return result


def top_processes(before, after, sample_s, count):
    rows = []
    for pid, (name, ticks_after) in after.items():
        prev = before.get(pid)
        if prev is None:
            continue
        d_ticks = ticks_after - prev[1]
        if d_ticks <= 0:
            continue
        pct = 100.0 * (d_ticks / CLK_TCK) / sample_s
        rows.append((pct, pid, name))
    rows.sort(reverse=True)
    return rows[:count]


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def human_bytes(n):
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024:
            return "{:.1f}{}".format(n, unit)
        n /= 1024
    return "{:.1f}PiB".format(n)


def human_rate(bytes_per_s):
    return human_bytes(bytes_per_s) + "/s"


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


def bar(pct, width=20):
    filled = max(0, min(width, round(pct / 100.0 * width)))
    return "[{}{}]".format("#" * filled, "-" * (width - filled))


def sparkline(history):
    top = max(history) if history else 100.0
    top = max(top, 1.0)
    return "".join(SPARK_BLOCKS[min(8, round(v / top * 8))] for v in history)


def color_for_percent(pct):
    if pct < 60:
        return 1
    if pct < 85:
        return 2
    return 3


def big_ip_lines(ip):
    glyphs = [BIG_DIGITS.get(ch, ("   ", "   ", "   ")) for ch in ip]
    return [" ".join(g[row] for g in glyphs) for row in range(3)]


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------


def safe_line(stdscr, row, text, attr=curses.A_NORMAL):
    max_y, max_x = stdscr.getmaxyx()
    if 0 <= row < max_y:
        try:
            stdscr.addnstr(row, 0, text, max(0, max_x - 1), attr)
        except curses.error:
            pass


def draw(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_YELLOW, -1)
    curses.init_pair(3, curses.COLOR_RED, -1)
    curses.init_pair(4, curses.COLOR_CYAN, -1)

    refresh_interval = REFRESH_INTERVAL_S
    hostname = socket.gethostname()
    cpu_history = deque(maxlen=HISTORY_LEN)
    net_before = read_net_bytes()
    proc_before = read_proc_cpu_times()

    while True:
        sample_s = min(0.3, refresh_interval)
        cpu_before = read_cpu_times()
        time.sleep(sample_s)
        cpu_after = read_cpu_times()
        net_after = read_net_bytes()
        proc_after = read_proc_cpu_times()

        try:
            ip = get_ip()
            mem_used, mem_total = get_memory()
            disk_used, disk_total = get_disk()
            uptime_s = get_uptime()
        except OSError:
            time.sleep(refresh_interval)
            continue

        cpu_pct = cpu_percent_from(cpu_before, cpu_after)
        mem_pct = 100.0 * mem_used / mem_total if mem_total else 0.0
        disk_pct = 100.0 * disk_used / disk_total if disk_total else 0.0
        cpu_history.append(cpu_pct)
        top = top_processes(proc_before, proc_after, sample_s, TOP_PROCESS_COUNT)
        proc_before = proc_after

        stdscr.erase()
        row = 0

        for line in big_ip_lines(ip):
            safe_line(stdscr, row, "  " + line, curses.color_pair(4) | curses.A_BOLD)
            row += 1
        row += 1

        width = 56
        safe_line(stdscr, row, "+" + "-" * width + "+"); row += 1

        def meter(label, pct, used_total=None):
            nonlocal row
            text = "| {:<5} {} {:5.1f}%".format(label, bar(pct), pct)
            if used_total:
                text += " {}".format(used_total)
            safe_line(stdscr, row, text.ljust(width + 1) + "|", curses.color_pair(color_for_percent(pct)))
            row += 1

        meter("CPU", cpu_pct)
        safe_line(stdscr, row, "| {:<5} {}".format("", sparkline(cpu_history)).ljust(width + 1) + "|")
        row += 1
        meter("MEM", mem_pct, "{}/{}".format(human_bytes(mem_used), human_bytes(mem_total)))
        meter("DISK", disk_pct, "{}/{}".format(human_bytes(disk_used), human_bytes(disk_total)))

        safe_line(stdscr, row, ("| Uptime: {}".format(human_duration(uptime_s))).ljust(width + 1) + "|")
        row += 1
        safe_line(stdscr, row, "+" + "-" * width + "+"); row += 1

        safe_line(stdscr, row, "+" + "-" * width + "+"); row += 1
        safe_line(stdscr, row, "| Network".ljust(width + 1) + "|"); row += 1
        for iface, (rx_after, tx_after) in net_after.items():
            rx_before, tx_before = net_before.get(iface, (rx_after, tx_after))
            rx_rate = max(0, rx_after - rx_before) / sample_s
            tx_rate = max(0, tx_after - tx_before) / sample_s
            text = "|  {:<8} down {:>12}  up {:>12}".format(iface, human_rate(rx_rate), human_rate(tx_rate))
            safe_line(stdscr, row, text.ljust(width + 1) + "|")
            row += 1
        net_before = net_after
        safe_line(stdscr, row, "+" + "-" * width + "+"); row += 1

        safe_line(stdscr, row, "+" + "-" * width + "+"); row += 1
        safe_line(stdscr, row, "| Top processes (CPU)".ljust(width + 1) + "|"); row += 1
        for pct, pid, name in top:
            text = "|  {:<6} {:<22} {:5.1f}%".format(pid, name[:22], pct)
            safe_line(stdscr, row, text.ljust(width + 1) + "|", curses.color_pair(color_for_percent(pct)))
            row += 1
        safe_line(stdscr, row, "+" + "-" * width + "+"); row += 1

        row += 1
        safe_line(stdscr, row, "{}  --  refresh {:.1f}s   [+/-] adjust   [q] quit to shell".format(hostname, refresh_interval))
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
    # Some terminals (e.g. kitty's default TERM=xterm-kitty) aren't in this
    # board's terminfo database, which makes curses.initscr() raise instead
    # of falling back -- retry once under a TERM every terminal emulator
    # can render correctly.
    try:
        curses.wrapper(draw)
    except curses.error:
        os.environ["TERM"] = "xterm-256color"
        try:
            curses.wrapper(draw)
        except curses.error as exc:
            print("Dashboard needs a terminal curses recognizes; tried xterm-256color too and it still failed: {}".format(exc))


if __name__ == "__main__":
    main()
