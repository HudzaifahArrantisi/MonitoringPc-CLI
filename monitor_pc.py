#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║                    MONITOR-PC  v3.0                         ║
║     Realtime PC Dashboard — Task Manager Style Graphs       ║
╚══════════════════════════════════════════════════════════════╝

Graph smooth ala Task Manager menggunakan asciichartpy.
Kurva melengkung (╭─╮ ╰─╯) — tidak kotak-kotak, tidak titik-titik.
Warna otomatis: hijau → kuning → merah sesuai beban.

Usage:
    python monitor_pc.py

Press Ctrl+C to exit.
"""

import platform
import re
import socket
import sys
import threading
import time
from collections import deque
from datetime import timedelta

import asciichartpy as acp
import psutil
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text



HISTORY_SIZE = 60
REFRESH_RATE = 1.0
GRAPH_HEIGHT = 10

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')



console = Console()
dynamic_graph_height = GRAPH_HEIGHT

cpu_history:    deque = deque([0.0] * HISTORY_SIZE, maxlen=HISTORY_SIZE)
ram_history:    deque = deque([0.0] * HISTORY_SIZE, maxlen=HISTORY_SIZE)
net_dl_history: deque = deque([0.0] * HISTORY_SIZE, maxlen=HISTORY_SIZE)
net_ul_history: deque = deque([0.0] * HISTORY_SIZE, maxlen=HISTORY_SIZE)
disk_read_history:  deque = deque([0.0] * HISTORY_SIZE, maxlen=HISTORY_SIZE)
disk_write_history: deque = deque([0.0] * HISTORY_SIZE, maxlen=HISTORY_SIZE)

_prev_net_io = None
_prev_time   = None
_prev_disk_io = None
_prev_disk_time = None

ping_latency = "Connecting..."
local_ip     = "Loading..."
top_cpu_processes = []
top_ram_processes = []


def adjust_history_size(current_deque: deque, target_size: int) -> deque:
    lst = list(current_deque)
    if len(lst) < target_size:
        lst = [0.0] * (target_size - len(lst)) + lst
    elif len(lst) > target_size:
        lst = lst[-target_size:]
    return deque(lst, maxlen=target_size)


def ping_worker():
    """
    Background daemon thread to check local IP and Ping latency to Google DNS (8.8.8.8).
    Runs every 3 seconds to avoid blocking the main UI thread.
    """
    global ping_latency, local_ip
    while True:
        # 1. Update Local IP Address
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = "127.0.0.1"

        # 2. Update Ping Latency via TCP connect to port 53 (DNS)
        try:
            t0 = time.time()
            s = socket.create_connection(("8.8.8.8", 53), timeout=1.5)
            s.close()
            latency = (time.time() - t0) * 1000
            ping_latency = f"{latency:.0f} ms"
        except Exception:
            ping_latency = "Offline / Timeout"

        time.sleep(3.0)


def process_worker():
    """
    Background daemon thread to scan and fetch top processes (CPU & Memory).
    Runs every 2 seconds. Reuses process objects to calculate CPU percentage accurately.
    """
    global top_cpu_processes, top_ram_processes
    procs = {}
    while True:
        try:
            current_procs = {}
            for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    pid = proc.info['pid']
                    if pid == 0: 
                        continue

                    p_obj = procs.get(pid)
                    if not p_obj:
                        p_obj = proc
                        p_obj.cpu_percent()  

                    cpu_pct = p_obj.cpu_percent()
                    mem_bytes = proc.info['memory_info'].rss if proc.info['memory_info'] else 0

                    current_procs[pid] = {
                        'pid': pid,
                        'name': proc.info['name'] or "Unknown",
                        'cpu': cpu_pct,
                        'mem': mem_bytes,
                        'proc_obj': p_obj
                    }
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass

            procs = {pid: info['proc_obj'] for pid, info in current_procs.items()}

            all_p = list(current_procs.values())
            
            top_cpu = sorted(all_p, key=lambda x: x['cpu'], reverse=True)[:3]
            top_ram = sorted(all_p, key=lambda x: x['mem'], reverse=True)[:3]

            top_cpu_processes = top_cpu
            top_ram_processes = top_ram
        except Exception:
            pass
        time.sleep(2.0)



def get_rich_color(pct: float) -> str:
    if pct < 50: return "green"
    if pct < 80: return "yellow"
    return "red"


def get_acp_color(pct: float):
    if pct < 50: return acp.green
    if pct < 80: return acp.yellow
    return acp.red


def get_styled_percent(pct: float) -> Text:
    return Text(f"{pct:5.1f}%", style=f"bold {get_rich_color(pct)}")



def format_bytes(n: float) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {u}"
        n /= 1024.0
    return f"{n:.1f} PB"


def format_speed(b: float) -> str:
    for u in ("B/s", "KB/s", "MB/s", "GB/s"):
        if abs(b) < 1024.0:
            return f"{b:.1f} {u}"
        b /= 1024.0
    return f"{b:.1f} TB/s"


def format_speed_short(val: float) -> str:
    if val <= 0:         return "0"
    if val < 1024:       return f"{val:.0f}B"
    if val < 1048576:    return f"{val/1024:.0f}K"
    if val < 1073741824: return f"{val/1048576:.0f}M"
    return f"{val/1073741824:.1f}G"


def format_uptime(boot_time: float) -> str:
    try:
        delta = timedelta(seconds=time.time() - boot_time)
        h, rem = divmod(delta.seconds, 3600)
        m, s   = divmod(rem, 60)
        parts  = []
        if delta.days > 0:
            parts.append(f"{delta.days}d")
        parts.append(f"{h:02d}h {m:02d}m {s:02d}s")
        return " ".join(parts)
    except Exception:
        return "N/A"


def auto_scale(max_val: float) -> float:
    if max_val <= 0: return 1024.0
    for t in [1024, 5120, 10240, 51200, 102400, 524288,
              1048576, 5242880, 10485760, 52428800, 104857600, 1073741824]:
        if max_val <= t: return float(t)
    return max_val



def build_chart(
    history,
    current_val: float = 0.0,
    max_val: float     = 100.0,
    is_speed: bool     = False,
    height: int        = GRAPH_HEIGHT,
) -> Text:
    data = list(history)
    if len(data) < 2:
        data = [0.0, 0.0]

    if max_val <= 0:
        max_val = 1.0

    pct_now = (current_val / max_val * 100) if is_speed else current_val
    color   = get_acp_color(pct_now)

    if is_speed:
        label_fmt = "{:6.0f}"
    else:
        label_fmt = "{:5.0f}%"

    cfg = {
        "height": height,
        "min":    0,
        "max":    max_val,
        "colors": [color],
        "format": label_fmt,
    }

    raw   = acp.plot(data, cfg)
    lines = raw.rstrip("\n").split("\n")

    visual_widths  = [len(_ANSI_RE.sub("", l)) for l in lines]
    max_visual_w   = max(visual_widths)

    short_w_list = [w for w in visual_widths if w < 20]
    y_prefix     = short_w_list[0] if short_w_list else 8

    body_w = max_visual_w - y_prefix
    gap    = max(0, body_w - 10)
    xaxis  = " " * y_prefix + "60s ago" + " " * gap + "now"

    raw += "\n" + xaxis
    return Text.from_ansi(raw)



def get_system_stats() -> dict:
    global _prev_net_io, _prev_time, _prev_disk_io, _prev_disk_time
    s = {}

    try:
        s["cpu"]          = psutil.cpu_percent(interval=0)
        s["cpu_per_core"] = psutil.cpu_percent(interval=0, percpu=True)
        freq              = psutil.cpu_freq()
        s["cpu_freq"]     = freq.current if freq else None
    except Exception:
        s.update(cpu=0.0, cpu_per_core=[], cpu_freq=None)

    try:
        m = psutil.virtual_memory()
        s.update(ram=m.percent, ram_used=m.used, ram_total=m.total, ram_available=m.available)
    except Exception:
        s.update(ram=0.0, ram_used=0, ram_total=0, ram_available=0)

    try:
        path = "C:\\" if platform.system() == "Windows" else "/"
        d    = psutil.disk_usage(path)
        s.update(disk_percent=d.percent, disk_used=d.used,
                 disk_total=d.total, disk_free=d.free, disk_path=path)
    except Exception:
        s.update(disk_percent=0.0, disk_used=0, disk_total=0, disk_free=0, disk_path="N/A")

    try:
        disk_io = psutil.disk_io_counters()
        now = time.time()
        if _prev_disk_io is not None and _prev_disk_time is not None:
            dt = now - _prev_disk_time
            if dt > 0:
                s["disk_read"]  = (disk_io.read_bytes - _prev_disk_io.read_bytes) / dt
                s["disk_write"] = (disk_io.write_bytes - _prev_disk_io.write_bytes) / dt
            else:
                s["disk_read"] = s["disk_write"] = 0.0
        else:
            s["disk_read"] = s["disk_write"] = 0.0
        _prev_disk_io = disk_io
        _prev_disk_time = now
    except Exception:
        s.update(disk_read=0.0, disk_write=0.0)

    try:
        net = psutil.net_io_counters()
        now = time.time()
        if _prev_net_io is not None and _prev_time is not None:
            dt = now - _prev_time
            if dt > 0:
                s["net_upload"]   = (net.bytes_sent - _prev_net_io.bytes_sent) / dt
                s["net_download"] = (net.bytes_recv - _prev_net_io.bytes_recv) / dt
            else:
                s["net_upload"] = s["net_download"] = 0.0
        else:
            s["net_upload"] = s["net_download"] = 0.0
        s["net_sent_total"] = net.bytes_sent
        s["net_recv_total"] = net.bytes_recv
        _prev_net_io = net
        _prev_time   = now
    except Exception:
        s.update(net_upload=0.0, net_download=0.0, net_sent_total=0, net_recv_total=0)

    try:
        bat = psutil.sensors_battery()
        if bat:
            s["battery_percent"] = bat.percent
            s["battery_plugged"]  = bat.power_plugged
            if   bat.secsleft == psutil.POWER_TIME_UNLIMITED: s["battery_time"] = "Charging"
            elif bat.secsleft == psutil.POWER_TIME_UNKNOWN:   s["battery_time"] = "Estimating..."
            else:
                mins, _ = divmod(bat.secsleft, 60)
                hrs, mins = divmod(mins, 60)
                s["battery_time"] = f"{int(hrs)}h {int(mins)}m remaining"
        else:
            s["battery_percent"] = None
    except Exception:
        s["battery_percent"] = None

    try:    s["process_count"] = len(psutil.pids())
    except: s["process_count"] = 0

    s["boot_time"]          = psutil.boot_time() if hasattr(psutil, "boot_time") else 0
    s["hostname"]           = platform.node() or "Unknown"
    s["os_info"]            = f"{platform.system()} {platform.release()}"
    s["python_version"]     = platform.python_version()
    s["cpu_name"]           = platform.processor() or "Unknown"
    s["cpu_cores_logical"]  = psutil.cpu_count(logical=True)  or 0
    s["cpu_cores_physical"] = psutil.cpu_count(logical=False) or 0
    return s



def build_cpu_panel(stats: dict) -> Panel:
    cpu   = stats["cpu"]
    color = get_rich_color(cpu)

    c = Table.grid(padding=0)
    c.add_column()

    hdr = Text()
    hdr.append("  CPU  ", style="bold white")
    hdr.append(f"{cpu:.1f}%", style=f"bold {color}")
    if stats.get("cpu_freq"):
        hdr.append(f"  │  {stats['cpu_freq']:.0f} MHz", style="dim")
    c.add_row(hdr)
    c.add_row(Text(""))

    c.add_row(build_chart(cpu_history, current_val=cpu, height=dynamic_graph_height))

    cores = stats.get("cpu_per_core", [])
    if cores:
        ct = Text("\n  ")
        for i, cp in enumerate(cores):
            ct.append(f"C{i}:", style="dim")
            ct.append(f"{cp:4.0f}% ", style=get_rich_color(cp))
            if (i + 1) % 6 == 0 and i < len(cores) - 1:
                ct.append("\n  ")
        c.add_row(ct)

    return Panel(c, title=f"[bold {color}]⬢ CPU[/bold {color}]",
                 border_style=color, padding=(0, 1))


def build_ram_panel(stats: dict) -> Panel:
    ram   = stats["ram"]
    color = get_rich_color(ram)

    c = Table.grid(padding=0)
    c.add_column()

    hdr = Text()
    hdr.append("  RAM  ", style="bold white")
    hdr.append(f"{ram:.1f}%", style=f"bold {color}")
    hdr.append(
        f"  │  {format_bytes(stats['ram_used'])} / {format_bytes(stats['ram_total'])}",
        style="dim"
    )
    c.add_row(hdr)
    c.add_row(Text(""))

    c.add_row(build_chart(ram_history, current_val=ram, height=dynamic_graph_height))

    detail = Text("\n  ")
    detail.append("Available: ", style="dim")
    detail.append(format_bytes(stats["ram_available"]), style="bold green")
    c.add_row(detail)

    return Panel(c, title=f"[bold {color}]⬡ Memory[/bold {color}]",
                 border_style=color, padding=(0, 1))


def build_network_panel(stats: dict) -> Panel:
    dl  = stats["net_download"]
    ul  = stats["net_upload"]
    all_speeds = list(net_dl_history) + list(net_ul_history)
    scaled_max = auto_scale(max(all_speeds) if all_speeds else 0)

    c = Table.grid(padding=0)
    c.add_column()

    hdr = Text()
    hdr.append("  ↓ ", style="bold bright_green")
    hdr.append(format_speed(dl), style="bold bright_green")
    hdr.append("  │  ↑ ", style="dim")
    hdr.append(format_speed(ul), style="bold cyan")
    c.add_row(hdr)
    c.add_row(Text(""))

    c.add_row(build_chart(net_dl_history, current_val=dl,
                          max_val=scaled_max, is_speed=True, height=dynamic_graph_height))

    total = Text("\n  ")
    total.append("Σ Recv: ", style="dim")
    total.append(format_bytes(stats["net_recv_total"]), style="cyan")
    total.append("  Σ Sent: ", style="dim")
    total.append(format_bytes(stats["net_sent_total"]), style="cyan")
    c.add_row(total)

    return Panel(c, title="[bold cyan]⇅ Network[/bold cyan]",
                 border_style="cyan", padding=(0, 1))


def build_disk_panel(stats: dict) -> Panel:
    pct   = stats["disk_percent"]
    color = get_rich_color(pct)
    read_speed  = stats.get("disk_read", 0.0)
    write_speed = stats.get("disk_write", 0.0)

    c = Table.grid(padding=0)
    c.add_column()

    hdr = Text()
    hdr.append("  Disk  ", style="bold white")
    hdr.append(f"{pct:.1f}%", style=f"bold {color}")
    hdr.append(
        f"  │  {format_bytes(stats['disk_used'])} / {format_bytes(stats['disk_total'])}",
        style="dim"
    )
    c.add_row(hdr)
    c.add_row(Text(""))

    p_grid = Table.grid(padding=(0, 1))
    p_grid.add_column(width=2)
    p_grid.add_column(width=30)
    p_grid.add_column()
    p_grid.add_row("", ProgressBar(total=100, completed=pct, width=30), get_styled_percent(pct))
    c.add_row(p_grid)
    c.add_row(Text(""))

    speeds = Text()
    speeds.append("  Read: ", style="dim")
    speeds.append(format_speed(read_speed), style="bold bright_green")
    speeds.append("  │  Write: ", style="dim")
    speeds.append(format_speed(write_speed), style="bold cyan")
    c.add_row(speeds)
    c.add_row(Text(""))

    all_disk_speeds = list(disk_read_history) + list(disk_write_history)
    scaled_max = auto_scale(max(all_disk_speeds) if all_disk_speeds else 0)
    combined_val = read_speed + write_speed
    
    combined_history = [r + w for r, w in zip(disk_read_history, disk_write_history)]
    c.add_row(build_chart(combined_history, current_val=combined_val,
                          max_val=scaled_max, is_speed=True, height=dynamic_graph_height))

    return Panel(c, title=f"[bold {color}]◆ Disk[/bold {color}]",
                 border_style=color, padding=(0, 1))


def build_system_panel(stats: dict) -> Panel:
    t = Table.grid(padding=(0, 2))
    t.add_column(min_width=12)
    t.add_column()

    ping_style = "bold yellow" if "ms" in ping_latency else "bold red"

    for label, val, style in [
        ("  Hostname",  stats["hostname"],          "bold white"),
        ("  OS",        stats["os_info"],            "white"),
        ("  Python",    stats["python_version"],     "white"),
        ("  CPU",       stats["cpu_name"],           "white"),
        ("  Cores",     f"{stats['cpu_cores_physical']}P / {stats['cpu_cores_logical']}L", "white"),
        ("  Uptime",    format_uptime(stats["boot_time"]),   "bold magenta"),
        ("  Processes", str(stats["process_count"]),          "bold cyan"),
        ("  Local IP",  local_ip,                    "bold green"),
        ("  Ping (8.8.8.8)", ping_latency,           ping_style),
    ]:
        t.add_row(Text(label, style="dim"), Text(val, style=style))

    if stats["battery_percent"] is not None:
        bc      = get_rich_color(100 - stats["battery_percent"])
        plugged = "⚡ Plugged In" if stats.get("battery_plugged") else "🔋 On Battery"
        t.add_row(
            Text("  Battery", style="dim"),
            Text(f"{stats['battery_percent']:.0f}%  {plugged}  {stats.get('battery_time','')}",
                 style=f"bold {bc}"),
        )
    else:
        t.add_row(Text("  Battery", style="dim"), Text("Not available", style="dim italic"))

    return Panel(t, title="[bold magenta]⊞ System Info[/bold magenta]",
                 border_style="magenta", padding=(0, 1))


def build_processes_panel() -> Panel:
    """
    Build processes panel to show Top 3 CPU and Memory consuming processes.
    """
    t = Table.grid(padding=(0, 1))
    t.add_column(min_width=24)
    t.add_column(min_width=24)

    cpu_t = Table(title="Top CPU Processes", show_header=True, header_style="bold green", box=None, padding=(0, 1))
    cpu_t.add_column("PID", style="dim", width=6)
    cpu_t.add_column("Name", width=10)
    cpu_t.add_column("CPU", justify="right", style="bold green", width=6)

    if top_cpu_processes:
        for p in top_cpu_processes:
            cpu_t.add_row(str(p['pid']), p['name'][:10], f"{p['cpu']:.1f}%")
    else:
        cpu_t.add_row("-", "Scanning...", "-")

    ram_t = Table(title="Top Memory Processes", show_header=True, header_style="bold cyan", box=None, padding=(0, 1))
    ram_t.add_column("PID", style="dim", width=6)
    ram_t.add_column("Name", width=10)
    ram_t.add_column("RAM", justify="right", style="bold cyan", width=8)

    if top_ram_processes:
        for p in top_ram_processes:
            ram_t.add_row(str(p['pid']), p['name'][:10], format_bytes(p['mem']))
    else:
        ram_t.add_row("-", "Scanning...", "-")

    t.add_row(cpu_t, ram_t)

    return Panel(t, title="[bold yellow]⚡ Top Processes[/bold yellow]",
                 border_style="yellow", padding=(0, 1))



def create_dashboard() -> Layout:
    width, height = console.size

    global dynamic_graph_height, cpu_history, ram_history, net_dl_history, net_ul_history, disk_read_history, disk_write_history
    
    target_history_size = max(20, (width // 2) - 14)
    dynamic_graph_height = max(5, ((height - 16) // 2) - 9)

    cpu_history = adjust_history_size(cpu_history, target_history_size)
    ram_history = adjust_history_size(ram_history, target_history_size)
    net_dl_history = adjust_history_size(net_dl_history, target_history_size)
    net_ul_history = adjust_history_size(net_ul_history, target_history_size)
    disk_read_history = adjust_history_size(disk_read_history, target_history_size)
    disk_write_history = adjust_history_size(disk_write_history, target_history_size)

    stats = get_system_stats()

    cpu_history.append(stats["cpu"])
    ram_history.append(stats["ram"])
    net_dl_history.append(stats["net_download"])
    net_ul_history.append(stats["net_upload"])
    disk_read_history.append(stats.get("disk_read", 0.0))
    disk_write_history.append(stats.get("disk_write", 0.0))

    layout = Layout()
    layout.height = max(20, height - 2)
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="top",    ratio=4),
        Layout(name="middle", ratio=4),
        Layout(name="bottom", size=13),
    )

    hdr = Text.from_markup(
        "  [bold bright_white]MONITOR-PC v3.0[/bold bright_white]"
        "  [dim]│[/dim]  [dim]Realtime Performance Dashboard[/dim]"
        "  [dim]│[/dim]  "
        f"[dim]{time.strftime('%Y-%m-%d %H:%M:%S')}[/dim]"
        "  [dim]│[/dim]  [dim italic]Ctrl+C to exit[/dim italic]"
    )
    layout["header"].update(Panel(hdr, style="bright_blue", border_style="bright_blue"))

    layout["top"].split_row(Layout(name="cpu", ratio=1), Layout(name="ram", ratio=1))
    layout["cpu"].update(build_cpu_panel(stats))
    layout["ram"].update(build_ram_panel(stats))

    layout["middle"].split_row(Layout(name="network", ratio=1), Layout(name="disk", ratio=1))
    layout["network"].update(build_network_panel(stats))
    layout["disk"].update(build_disk_panel(stats))

    layout["bottom"].split_row(
        Layout(name="system", ratio=1),
        Layout(name="processes", ratio=1)
    )
    layout["system"].update(build_system_panel(stats))
    layout["processes"].update(build_processes_panel())
    return layout



def main():
    console = Console()
    psutil.cpu_percent(interval=0)
    console.clear()

    threading.Thread(target=ping_worker, daemon=True).start()
    threading.Thread(target=process_worker, daemon=True).start()

    try:
        with Live(create_dashboard(), console=console,
                  refresh_per_second=1, screen=False, transient=False) as live:
            while True:
                time.sleep(REFRESH_RATE)
                live.update(create_dashboard())
    except KeyboardInterrupt:
        console.clear()
        console.print(Panel(
            Text.from_markup(
                "[bold green]✔ Monitor-PC stopped gracefully.[/bold green]\n"
                "[dim]Thank you for using Monitor-PC v3.0![/dim]"
            ),
            border_style="green", padding=(1, 2),
        ))
        sys.exit(0)


if __name__ == "__main__":
    main()