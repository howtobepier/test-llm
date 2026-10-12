from __future__ import annotations

import platform
import shutil
from datetime import datetime

import psutil

from app.tools.registry import ToolResult, register


@register("system_status")
def system_status() -> ToolResult:
    vm = psutil.virtual_memory()
    disk = shutil.disk_usage(".")
    data = {
        "os": platform.platform(),
        "python": platform.python_version(),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "ram_total_gb": round(vm.total / (1024**3), 2),
        "ram_available_gb": round(vm.available / (1024**3), 2),
        "ram_percent": vm.percent,
        "disk_free_gb": round(disk.free / (1024**3), 2),
        "time": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    summary = (
        f"CPU {data['cpu_percent']}% · RAM libera {data['ram_available_gb']} GB "
        f"({100 - data['ram_percent']:.0f}%) · disco libero {data['disk_free_gb']} GB"
    )
    return ToolResult(ok=True, summary=summary, data=data)


@register("now")
def now() -> ToolResult:
    dt = datetime.now().astimezone()
    giorni = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
    mesi = [
        "gennaio",
        "febbraio",
        "marzo",
        "aprile",
        "maggio",
        "giugno",
        "luglio",
        "agosto",
        "settembre",
        "ottobre",
        "novembre",
        "dicembre",
    ]
    text = (
        f"Sono le {dt.strftime('%H:%M')} di {giorni[dt.weekday()]} "
        f"{dt.day} {mesi[dt.month - 1]} {dt.year}"
    )
    return ToolResult(ok=True, summary=text, data={"iso": dt.isoformat()})
