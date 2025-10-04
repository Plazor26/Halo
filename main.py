# main.py
import os
import wave
import time
import datetime
import pyaudio
import json
import re
from dotenv import load_dotenv
from pathlib import Path

from halo_core.voice.wakeword import WakeWordDetector
from halo_core.voice.recognizer import LocalSTT
from halo_core.voice.tts import TTS
from halo_core.llm.local_llm import LocalLLM
from halo_core.skills import execute_intents

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
# LLM output cleanup (no heuristics on user text)
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
    Accept shapes like:
      - [{"action": "...", "target": "..."}]
      - ["set_volume", "set_volume_level:50"]
      - [{"type":"set_volume","value":"50"}]
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
        # last resort: remove braces so we don't read JSON aloud
        stripped = re.sub(r"[\{\}\[\]]", "", stripped)

    return stripped.strip() or "..."


# ───────────────────────────────
# LLM prompting (no regex fallbacks)
# ───────────────────────────────

def _actions_catalog_text(action_map: dict) -> str:
    """
    Turn action_map.json into a compact, unambiguous catalog for the prompt.
    It’s okay if the JSON only has names; we’ll still list them clearly.
    """
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
    """
    A strict, example-rich prompt that forces valid JSON with (reply, intents[]).
    """
    return f"""{personality}

You are Halo — a witty, tsundere desktop assistant.
User said: "{user_text}"

VALID ACTIONS CATALOG (pick only from these 'action' names; 'target' is optional unless obvious):
{actions_catalog}

You must return ONLY a JSON object with exactly these keys:
- "reply": a short tsundere sentence to say aloud (no JSON, no code fences)
- "intents": an array of objects, each: {{"action": "<valid_action_name>", "target": <string|number|null>}}

STRICT RULES:
- Output ONLY the JSON object (no code fences, no explanation).
- "intents" MUST be an array. If no action is needed, use [].
- For volume: use {{"action":"set_volume","target": 0-100}} as a number (not a string).
- For websites: use {{"action":"open_website","target":"example.com"}} or a full URL.
- Keep "reply" under ~16 words, tsundere tone, no JSON or backticks.

EXAMPLES (these are EXAMPLES; do NOT include them in output):

User: "set volume to 50%"
{{
  "reply": "Hmph! Fine, 50%. Happy now?",
  "intents": [{{"action":"set_volume","target":50}}]
}}

User: "open youtube"
{{
  "reply": "Tch… fine. Opening YouTube.",
  "intents": [{{"action":"open_website","target":"youtube.com"}}]
}}

Now respond for the actual user request as JSON:
"""


def _llm_repair_json_prompt(personality: str, actions_catalog: str, bad_output: str) -> str:
    """
    If the model messed up the format, ask it to repair its own output.
    Still no code fences, still strict keys.
    """
    return f"""{personality}

Your previous output was not valid JSON. Repair it.

VALID ACTIONS CATALOG:
{actions_catalog}

Return ONLY a valid JSON object with keys "reply" (string) and "intents" (array of objects with 'action' and optional 'target').
- For volume: set_volume target MUST be a number 0-100 (not a string).
- No code fences, no extra text.

Here is what you produced:
{bad_output}

Return just the corrected JSON:
"""


def llm_parse_and_reply(llm: LocalLLM, personality: str, action_map: dict, user_text: str):
    """
    Ask LLM to produce clean JSON (reply + intents). If it's messy,
    use a one-shot LLM "repair" pass (still LLM, not regex/heuristics).
    """
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
        # Ask LLM to repair its own output into valid JSON
        repair_prompt = _llm_repair_json_prompt(personality, actions_catalog, cleaned)
        repaired = llm.generate(repair_prompt, stream=False).strip()
        repaired_clean = _strip_code_fences(repaired)
        repaired_json = _extract_first_json_object(repaired_clean) or repaired_clean
        try:
            try_parse(repaired_json)
        except Exception:
            # As absolute last resort: speak something short; no intents (no action).
            reply_text = sanitize_reply(_extract_reply_from_text(repaired_clean) or repaired_clean)
            intents = []

    # Final safety: ensure reply is speakable text (never JSON)
    reply_text = sanitize_reply(reply_text)
    return {"reply": reply_text, "intents": intents}


def main():
    log("Initializing Halo Voice Core...", "STAGE")

    # 🌿 Wake word
    wake = WakeWordDetector(ACCESS_KEY, keyword_path=CUSTOM_KEYWORD_PATH)
    log("Halo wake word detector initialized ✨", "SUCCESS")

    # 🧠 STT
    stt = LocalSTT()
    log("Whisper recognizer ready 🧠", "SUCCESS")

    # 🗣️ TTS
    tts = TTS()
    log("TTS engine ready 🗣️", "SUCCESS")

    # 🤖 LLM
    llm = LocalLLM(model="gemma3:4b")
    log("LLM ready 🧠", "SUCCESS")

    # ✨ Personality + Action Map
    personality = load_personality()
    log("Halo personality loaded 💫", "SUCCESS")
    action_map = load_action_map()

    log("🌟 Halo is now listening for your call...", "STAGE")

    try:
        while True:
            start_time = datetime.datetime.now()
            log(f"🕒 Command started at {start_time.strftime('%H:%M:%S')}", "STAGE")

            # 1️⃣ Wake word
            wake.listen_for_wake_word()
            time.sleep(0.5)

            # 2️⃣ Record
            audio_file = record_audio()

            # 3️⃣ STT
            log("🧠 Transcribing...", "STAGE")
            text = stt.transcribe(audio_file).strip()
            print(f"\033[94m[TRANSCRIPT] → {text if text else '(no speech detected)'}\033[0m")
            if not text:
                continue

            # 4️⃣ LLM: decide + reply (no regex fallbacks)
            log("🧠 LLM reasoning...", "STAGE")
            llm_result = llm_parse_and_reply(llm, personality, action_map, text)
            reply_text = llm_result["reply"]
            intents = llm_result["intents"]
            print(f"\033[93m[LLM INTENTS] → {intents}\033[0m")

            # 5️⃣ Execute skills (skills return None by design)
            execute_intents(intents)

            # 6️⃣ Speak once (sanitized human text)
            log(f"Halo: {reply_text}", "STAGE")
            tts.speak(reply_text)

            end_time = datetime.datetime.now()
            elapsed = (end_time - start_time).total_seconds()
            log(f"🏁 Command finished at {end_time.strftime('%H:%M:%S')} — took {elapsed:.2f}s", "SUCCESS")

    except KeyboardInterrupt:
        log("Exiting cleanly (Ctrl+C).", "WARN")
    finally:
        wake.close()


if __name__ == "__main__":
    main()
