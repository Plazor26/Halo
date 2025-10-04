# main.py
import os
import wave
import time
import datetime
import pyaudio
from dotenv import load_dotenv
from pathlib import Path

from halo_core.voice.wakeword import WakeWordDetector
from halo_core.voice.recognizer import LocalSTT
from halo_core.voice.tts import TTS
from halo_core.llm.local_llm import LocalLLM
from halo_core.llm.intent_parser import IntentParser
from halo_core.skills import execute_intents

# 🌿 Load environment variables
env_path = Path(__file__).resolve().parent / "configs" / ".env"
load_dotenv(dotenv_path=env_path)
ACCESS_KEY = os.getenv("PORCUPINE_ACCESS_KEY")
if not ACCESS_KEY:
    raise ValueError("❌ Missing PORCUPINE_ACCESS_KEY in .env file!")

CUSTOM_KEYWORD_PATH = "halo_core/voice/models/halo.ppn"
PERSONALITY_PATH = "configs/personality.txt"

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


def main():
    log("Initializing Halo Voice Core...", "STAGE")

    # 🌿 Wake word
    wake = WakeWordDetector(ACCESS_KEY, keyword_path=CUSTOM_KEYWORD_PATH)
    log("Halo wake word detector initialized ✨", "SUCCESS")

    # 🧠 Speech to text
    stt = LocalSTT()
    log("Whisper recognizer ready 🧠", "SUCCESS")

    # 🗣️ Text to speech
    tts = TTS()
    log("TTS engine ready 🗣️", "SUCCESS")

    # 🤖 LLM + Intent Parser
    llm = LocalLLM(model="gemma3:4b")
    parser = IntentParser(llm=llm)
    log("LLM + Intent Parser ready 🧭", "SUCCESS")

    # ✨ Personality
    personality = load_personality()
    log("Halo personality loaded 💫", "SUCCESS")

    log("🌟 Halo is now listening for your call...", "STAGE")

    try:
        while True:
            # ⏰ Start time
            start_time = datetime.datetime.now()
            log(f"🕒 Command started at {start_time.strftime('%H:%M:%S')}", "STAGE")

            # 1️⃣ Wake word detection
            wake.listen_for_wake_word()
            time.sleep(0.5)

            # 2️⃣ Record voice
            audio_file = record_audio()

            # 3️⃣ Transcribe
            log("🧠 Transcribing...", "STAGE")
            text = stt.transcribe(audio_file).strip()
            print(f"\033[94m[TRANSCRIPT] → {text if text else '(no speech detected)'}\033[0m")

            if not text:
                continue

            # 4️⃣ Intent Parsing
            log("🧭 Parsing intent...", "STAGE")
            intents = parser.parse(text)
            print(f"\033[93m[INTENTS] → {intents}\033[0m")

            # 5️⃣ Execute skills
            skill_responses = execute_intents(intents.get("intents", []))
            skill_responses = [r for r in skill_responses if r]  # clean None/empty

            # 6️⃣ Pick reply text
            if skill_responses:
                reply_text = skill_responses[0]
            else:
                response_prompt = f"{personality}\nUser said: \"{text}\"\nHalo's reply:"
                reply_text = llm.generate(response_prompt, stream=False).strip()

            # 7️⃣ Speak once
            log(f"Halo: {reply_text}", "STAGE")
            tts.speak(reply_text)

            # ⏱️ End time
            end_time = datetime.datetime.now()
            elapsed = (end_time - start_time).total_seconds()
            log(f"🏁 Command finished at {end_time.strftime('%H:%M:%S')} — took {elapsed:.2f}s", "SUCCESS")

    except KeyboardInterrupt:
        log("Exiting cleanly (Ctrl+C).", "WARN")
    finally:
        wake.close()


if __name__ == "__main__":
    main()
