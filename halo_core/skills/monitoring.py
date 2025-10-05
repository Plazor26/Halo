# halo_core/skills/monitoring.py
import psutil
import shutil
import os

def _format_bytes(n: int) -> str:
    # Friendly bytes formatter
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if n < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"

def check_status(target=None):
    """
    Returns a snapshot of CPU, RAM, Disk usage.
    Extend with GPU/temps later if you want (e.g., nvidia-ml-py or wmi).
    """
    cpu = psutil.cpu_percent(interval=0.4)
    vm = psutil.virtual_memory()
    total = _format_bytes(vm.total)
    used = _format_bytes(vm.used)
    avail = _format_bytes(vm.available)

    # Disk: pick system drive
    system_drive = os.path.splitdrive(os.getcwd())[0] or "C:"
    total_d, used_d, free_d = shutil.disk_usage(system_drive + os.sep)
    disk_total = _format_bytes(total_d)
    disk_used = _format_bytes(used_d)
    disk_free = _format_bytes(free_d)

    procs = len(psutil.pids())

    status = {
        "cpu_percent": cpu,
        "mem": {"total": total, "used": used, "available": avail, "percent": vm.percent},
        "disk": {"drive": system_drive, "total": disk_total, "used": disk_used, "free": disk_free},
        "processes": procs
    }
    # Return a concise string for TTS + HUD
    summary = (f"CPU {cpu:.0f}% • RAM {vm.percent:.0f}% "
               f"({used}/{total}) • Disk {system_drive} {disk_used}/{disk_total} "
               f"free {disk_free} • {procs} processes")
    return {"status": status, "summary": summary}
