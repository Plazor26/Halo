# halo_core/voice/recognizer.py
import subprocess
import tempfile
import os
import uuid
import time

class LocalSTT:
    def __init__(
        self,
        model=r"./whisper/ggml-small.bin",
        exe=r"./whisper/whisper-cli.exe",
        threads=8
    ):
        self.model = model
        self.exe = exe
        self.threads = threads

    def transcribe(self, audio_path):
        """Fast, silent transcription using whisper-cli (no VAD)."""
        base_result = os.path.join(tempfile.gettempdir(), f"halo_stt_{uuid.uuid4().hex}")

        cmd = [
            self.exe,
            "-m", self.model,
            "-f", audio_path,
            "-otxt",
            "-of", base_result,
            "-t", str(self.threads),
            "--no-timestamps",
            "--no-fallback",
            "--no-prints"
        ]

        start = time.time()
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elapsed = time.time() - start

        txt_path = base_result + ".txt"
        if not os.path.exists(txt_path):
            print(f"[STT] ❌ No transcript (took {elapsed:.2f}s)")
            return ""

        with open(txt_path, "r", encoding="utf-8") as f:
            text = f.read().strip()

        try:
            os.remove(txt_path)
        except FileNotFoundError:
            pass

        print(f"[STT] ⏱️ Transcription took {elapsed:.2f}s")
        if text:
            print(f"[STT] 📝 \"{text}\"")
        else:
            print("[STT] (no speech detected)")

        return text
