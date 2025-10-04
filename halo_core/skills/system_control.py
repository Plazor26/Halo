import os
import subprocess
import ctypes
import webbrowser

# 📴 --- Power Controls --- 📴

def shutdown():
    """Shuts down the computer gracefully."""
    subprocess.run(["shutdown", "/s", "/t", "5"])
    return None  # Let LLM handle the response

def restart():
    """Restarts the computer."""
    subprocess.run(["shutdown", "/r", "/t", "5"])
    return None

def sleep():
    """Puts the system to sleep."""
    ctypes.windll.PowrProf.SetSuspendState(0, 0, 0)
    return None

# 🔈 --- Volume Controls --- 🔈

def mute_system():
    """Mutes the system volume."""
    subprocess.run(['powershell', '-Command',
                    "(new-object -com wscript.shell).SendKeys([char]173)"])
    return None

def unmute_system():
    """Unmutes the system volume."""
    subprocess.run(['powershell', '-Command',
                    "(new-object -com wscript.shell).SendKeys([char]173)"])
    return None

def set_volume(target: int):
    """
    Sets the system volume to a given percentage (0–100) on Windows.
    """
    if target is None:
        return None

    try:
        volume = max(0, min(100, int(target)))  # Clamp between 0–100

        # 1️⃣ Set to 0 first by sending 'volume down' 50 times
        subprocess.run(
            ['powershell', '-Command',
             f"for ($i=0; $i -lt 50; $i++) {{ (new-object -com wscript.shell).SendKeys([char]174) }}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        # 2️⃣ Raise volume to target by sending 'volume up'
        presses = int(volume / 2)  # each press ≈ 2%
        subprocess.run(
            ['powershell', '-Command',
             f"for ($i=0; $i -lt {presses}; $i++) {{ (new-object -com wscript.shell).SendKeys([char]175) }}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        return None

    except Exception as e:
        return f"Ugh… I tried to change the volume but something broke: {e}"

# 🪄 --- Task & App Management --- 🪄

def close_all_apps():
    """Closes all open windows/apps except system essentials."""
    subprocess.run(['powershell', '-Command',
                    'Get-Process | Where-Object {$_.MainWindowTitle -ne ""} | ForEach-Object {Stop-Process $_.Id -Force}'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return None

def open_task_manager():
    """Opens the Windows Task Manager."""
    subprocess.Popen(["taskmgr"])
    return None

# 🌐 --- Browser / Web --- 🌐

def open_website(target):
    """
    Opens the default browser with a given site.
    Target can be 'youtube', 'google', or a full URL.
    """
    if not target:
        return None

    if not target.startswith("http"):
        target = f"https://{target}"

    webbrowser.open(target)
    return None

# ⏯ --- Media Controls --- ⏯

def play_pause_media():
    """Toggles play/pause of current media using media key simulation."""
    subprocess.run(['powershell', '-Command',
                    '(new-object -com wscript.shell).SendKeys([char]179)'])
    return None
