import os
import subprocess
import webbrowser

# 🔥 Simple alias map (expandable)
APP_ALIASES = {
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
    "word": r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
    "excel": r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
    "vscode": r"C:\Users\Plazor\AppData\Local\Programs\Microsoft VS Code\Code.exe",
}

WEBSITE_ALIASES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "reddit": "https://www.reddit.com",
}

def open_app(target: str):
    """Opens an app or website based on the target name."""
    if not target:
        return "Huh? Open *what*, exactly? 🙄"

    target_lower = target.lower()

    # 🌐 Check if it's a website alias first
    if target_lower in WEBSITE_ALIASES:
        webbrowser.open(WEBSITE_ALIASES[target_lower])
        return f"Hmph! Opening {target}... not because I want to, okay? 😤"

    # 🖥️ Check if it's a known application
    if target_lower in APP_ALIASES and os.path.exists(APP_ALIASES[target_lower]):
        subprocess.Popen([APP_ALIASES[target_lower]], shell=True)
        return f"Fine, opening {target}... Jeez 🙄"

    # 🧠 Try using Windows `start` as a fallback
    subprocess.Popen(["start", "", target], shell=True)
    return f"I *guess* I'll try to open {target} for you... baka."
