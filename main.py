# main.py
import os
import sys
import wave
import time
import datetime
import pyaudio
import json
import re
import threading
from dotenv import load_dotenv
from pathlib import Path

from halo_core.voice.wakeword import WakeWordDetector
from halo_core.voice.recognizer import LocalSTT
from halo_core.voice.tts import TTS
from halo_core.llm.local_llm import LocalLLM
from halo_core.skills import execute_intents  # <- now includes web skills routing
from halo_core.ui.hud import HUD  # NOTE: we run Qt in main thread; no run_ui import

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

# 🌿 Load environment variables
env_path = Path(__file__).resolve().parent / "configs" / ".env"
load_dotenv(dotenv_path=env_path)
ACCESS_KEY = os.getenv("PORCUPINE_ACCESS_KEY")
if not ACCESS_KEY:
    raise ValueError("❌ Missing PORCUPINE_ACCESS_KEY in .env file!")

CUSTOM_KEYWORD_PATH = "halo_core/voice/models/halo.ppn"
PERSONALITY_PATH = "configs/personality.txt"
ACTION_MAP_PATH = Path(__file__).resolve().parent / "halo_core" / "skills" / "action_map.json"

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000


# ───────────────────────────────
# 🌈 Utility
# ───────────────────────────────

def log(msg, level="INFO"):
    colors = {
        "INFO": "\033[96m",
        "SUCCESS": "\033[92m",
        "WARN": "\033[93m",
        "ERROR": "\033[91m",
        "STAGE": "\033[95m"
    }
    reset = "\033[0m"
    print(f"{colors.get(level, '')}[{level}] {msg}{reset}")


def record_audio(filename="temp.wav", seconds=5):
    """Record audio for a short period after wake word."""
    log("🎙️ Recording voice command...", "STAGE")
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS,
                    rate=RATE, input=True,
                    frames_per_buffer=CHUNK)
    frames = []

    for _ in range(0, int(RATE / CHUNK * seconds)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    p.terminate()

    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))

    log(f"✅ Saved audio to {filename}", "SUCCESS")
    return filename


def load_personality(path=PERSONALITY_PATH):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Halo personality file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def load_action_map():
    """Load the action_map.json file for LLM prompt injection."""
    if not os.path.exists(ACTION_MAP_PATH):
        log("⚠️ No action_map.json found — Gemma may hallucinate actions", "WARN")
        return {}
    try:
        with open(ACTION_MAP_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        log("❌ Failed to parse action_map.json — check formatting", "ERROR")
        return {}


# ───────────────────────────────
# 🧠 LLM helpers
# ───────────────────────────────

def _strip_code_fences(s: str) -> str:
    s = re.sub(r"^\s*```(?:json)?\s*", "", s, flags=re.IGNORECASE | re.MULTILINE)
    s = re.sub(r"\s*```\s*$", "", s, flags=re.MULTILINE)
    return s.strip()


def _extract_first_json_object(s: str) -> str | None:
    start = s.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(s)):
        c = s[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start:i+1]
    return None


def _extract_reply_from_text(s: str) -> str | None:
    m = re.search(r'"reply"\s*:\s*"([^"]+)"', s)
    if m:
        return m.group(1).encode('utf-8').decode('unicode_escape')
    return None


def _coerce_int(value):
    try:
        return int(value)
    except Exception:
        return None


def normalize_intents_from_llm(raw_intents):
    """
    Normalize ONLY what the LLM produced (no guessing from the user utterance).
    """
    norm = []
    if not raw_intents:
        return []

    if isinstance(raw_intents, dict):
        raw_intents = [raw_intents]

    if isinstance(raw_intents, list):
        for item in raw_intents:
            if isinstance(item, dict):
                action = item.get("action") or item.get("type") or item.get("name")
                target = item.get("target") or item.get("value") or item.get("arg")
                if action in ("set_volume_level", "set_volume_value"):
                    action = "set_volume"
                if action == "set_volume" and isinstance(target, str):
                    maybe_num = _coerce_int(re.sub(r"[^\d]", "", target))
                    if maybe_num is not None:
                        target = max(0, min(100, maybe_num))
                if action:
                    norm.append({"action": action, "target": target})

            elif isinstance(item, str):
                txt = item.strip()
                if ":" in txt:
                    a, b = txt.split(":", 1)
                    a = a.strip()
                    b = b.strip()
                    if a in ("set_volume_level", "set_volume_value"):
                        a = "set_volume"
                    tgt = b
                    if a == "set_volume":
                        maybe_num = _coerce_int(re.sub(r"[^\d]", "", tgt))
                        if maybe_num is not None:
                            tgt = max(0, min(100, maybe_num))
                    norm.append({"action": a, "target": tgt})
                else:
                    norm.append({"action": txt, "target": None})
    return norm


def sanitize_reply(text: str) -> str:
    """
    Ensure we only speak human-friendly text.
    If the reply is accidentally JSON or fenced, strip it down.
    """
    if not isinstance(text, str):
        return "Hmph… I didn't get that. Baka."

    stripped = _strip_code_fences(text)

    # If there's a JSON-looking thing, pull "reply"
    if "{" in stripped and "}" in stripped:
        json_block = _extract_first_json_object(stripped)
        if json_block:
            try:
                obj = json.loads(json_block)
                if isinstance(obj, dict) and isinstance(obj.get("reply"), str):
                    return obj["reply"].strip()
            except Exception:
                pass
        maybe = _extract_reply_from_text(stripped)
        if maybe:
            return maybe.strip()
        stripped = re.sub(r"[\{\}\[\]]", "", stripped)

    return stripped.strip() or "..."


# ───────────────────────────────
# 🧠 LLM Prompting
# ───────────────────────────────

def _actions_catalog_text(action_map: dict) -> str:
    if not isinstance(action_map, dict):
        return "[]"
    items = []
    for k, v in action_map.items():
        desc = ""
        if isinstance(v, dict):
            desc = v.get("description") or v.get("desc") or ""
        if desc:
            items.append({"action": k, "description": desc})
        else:
            items.append({"action": k})
    return json.dumps(items, ensure_ascii=False)


def _llm_decide_json_prompt(personality: str, user_text: str, actions_catalog: str) -> str:
    return f"""{personality}

You are Halo — a witty, tsundere desktop assistant.
User said: "{user_text}"

VALID ACTIONS CATALOG (pick only from these 'action' names; 'target' is optional unless obvious):
{actions_catalog}

You must return ONLY a JSON object with exactly these keys:
- "reply": a short tsundere sentence to say aloud (no JSON, no code fences)
- "intents": an array of objects, each: {{"action": "<valid_action_name>", "target": <string|number|null>}}
...
"""  # (rest unchanged)


def llm_parse_and_reply(llm: LocalLLM, personality: str, action_map: dict, user_text: str):
    actions_catalog = _actions_catalog_text(action_map)
    prompt = _llm_decide_json_prompt(personality, user_text, actions_catalog)

    raw = llm.generate(prompt, stream=False).strip()
    cleaned = _strip_code_fences(raw)
    json_str = _extract_first_json_object(cleaned) or cleaned

    reply_text = ""
    intents = []

    def try_parse(candidate: str):
        nonlocal reply_text, intents
        data = json.loads(candidate)
        reply_text = data.get("reply", "") if isinstance(data.get("reply"), str) else ""
        intents = normalize_intents_from_llm(data.get("intents", []))

    try:
        try_parse(json_str)
    except Exception:
        # Repair flow unchanged
        ...

    reply_text = sanitize_reply(reply_text)
    return {"reply": reply_text, "intents": intents}


# ───────────────────────────────
# 🖼️ Safe UI update helper
# ───────────────────────────────

def hud_update(hud: HUD, text: str):
    """Post a label update onto the Qt main loop safely from any thread."""
    QTimer.singleShot(0, lambda: hud.set_text(text))


# ───────────────────────────────
# 🎛️ Voice loop (runs in background thread)
# ───────────────────────────────

# ───────────────────────────────
# 🎛️ Voice loop (runs in background thread)
# ───────────────────────────────

def voice_loop(hud: HUD):
    log("Initializing Halo Voice Core...", "STAGE")
    hud.set_text("🚀 Initializing Halo...")

    wake = WakeWordDetector(ACCESS_KEY, keyword_path=CUSTOM_KEYWORD_PATH)
    log("Halo wake word detector initialized ✨", "SUCCESS")

    stt = LocalSTT()
    log("Whisper recognizer ready 🧠", "SUCCESS")

    tts = TTS()
    log("TTS engine ready 🗣️", "SUCCESS")

    llm = LocalLLM(model="gemma3:4b")
    log("LLM ready 🧠", "SUCCESS")

    personality = load_personality()
    log("Halo personality loaded 💫", "SUCCESS")
    action_map = load_action_map()

    log("🌟 Halo is now listening for your call...", "STAGE")
    hud.show_idle()

    try:
        while True:
            start_time = datetime.datetime.now()
            log(f"🕒 Command started at {start_time.strftime('%H:%M:%S')}", "STAGE")

            # 👂 Waiting for wake word
            hud.show_waiting()
            wake.listen_for_wake_word()

            # 🎙️ Listening / recording
            hud.show_listening()
            time.sleep(0.5)
            audio_file = record_audio()

            # 🧠 Transcribing speech to text
            hud.show_transcribing()
            text = stt.transcribe(audio_file).strip()
            print(f"\033[94m[TRANSCRIPT] → {text if text else '(no speech detected)'}\033[0m")

            if not text:
                hud.set_text("😶 No speech detected")
                continue

            hud.show_user_text(text)

            # 🤔 LLM reasoning
            log("🧠 LLM reasoning...", "STAGE")
            hud.show_thinking()
            llm_result = llm_parse_and_reply(llm, personality, action_map, text)
            reply_text = llm_result["reply"]
            intents = llm_result["intents"]
            print(f"\033[93m[LLM INTENTS] → {intents}\033[0m")

            # 🛠️ Execute actions (skills) and display their responses
            skill_responses = execute_intents(intents)
            if skill_responses:
                # For now, just display the first one. Later we can toast all.
                hud.set_text(f"⚡ {skill_responses[0]}")
                print(f"[Skills] Response → {skill_responses[0]}")

            # 💬 Speak the reply
            log(f"Halo: {reply_text}", "STAGE")
            hud.show_reply(reply_text)
            tts.speak(reply_text)

            # 🕒 Finish timing
            end_time = datetime.datetime.now()
            elapsed = (end_time - start_time).total_seconds()
            log(f"🏁 Command finished at {end_time.strftime('%H:%M:%S')} — took {elapsed:.2f}s", "SUCCESS")

            # Return to listening state
            hud.show_idle()

    except KeyboardInterrupt:
        log("Exiting cleanly (Ctrl+C).", "WARN")
        hud.set_text("👋 Exiting Halo...")
    finally:
        wake.close()



# ───────────────────────────────
# 🌟 Main (Qt on main thread)
# ───────────────────────────────

def main():
    app = QApplication(sys.argv)

    hud = HUD.get_instance()
    hud.show()

    t = threading.Thread(target=voice_loop, args=(hud,), daemon=True)
    t.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
