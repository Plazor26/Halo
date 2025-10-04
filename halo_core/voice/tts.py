# halo_core/voice/tts.py
import subprocess
import tempfile
import os
import re
import time
import json

class TTS:
    def __init__(
        self,
        piper_path=r"C:\Tools\piper\piper.exe",
        model_path=r"C:\Tools\piper\en_US-amy-medium.onnx"
    ):
        self.piper_path = piper_path
        self.model_path = model_path

        # IPA dictionary for special vocalizations (used only if the entire text matches)
        self.ipa_dict = {
            "hmph": "ˈm̩mf",   # nasal "mmph" sound
            "tch": "t͡ʃ",      # sharp 'tch' click
        }

    def _preprocess_text(self, text: str) -> str:
        """
        Clean and tsundere-ify text for Piper.
        Converts stage directions, replaces common anime-esque interjections
        with phonetic approximations that Piper pronounces more naturally.
        """
        # 🎭 Replace stage directions like *opens browser* → (opens browser)
        text = re.sub(r"\*(.*?)\*", r"(\1)", text)

        # 💬 Tsundere replacements
        replacements = {
            r"\bhmph\b": "Hmf!",
            r"\bHmph\b": "Hmf!",
            r"\bMou~\b": "Moo~",
            r"\bmou~\b": "Moo~",
            r"\bAra~\b": "Ah-rah~",
            r"\bara~\b": "Ah-rah~",
            r"\bGeez\b": "Jeez",
            r"\bgeeze\b": "Jeez",
            r"\bBaka\b": "Baka!",
            r"\bbaka\b": "Baka!",
            r"\bUgh+\b": "Ughh",
            r"\bEhh+\b": "Eh",
            r"\bTch\b": "Tsk",
        }

        for pattern, repl in replacements.items():
            text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

        # 🧹 Clean extra symbols/spaces
        text = text.replace("*", "")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _try_get_ipa_json(self, text: str):
        """
        If the entire text is a special token like 'Hmph',
        return Piper phoneme JSON. Otherwise, None.
        """
        key = text.strip().lower()
        if key in self.ipa_dict:
            ipa = self.ipa_dict[key]
            return json.dumps({"phonemes": ipa}, ensure_ascii=False)
        return None

    def speak(self, text: str):
        """Generate and play speech with Piper (no popup media players)."""
        if not text or not text.strip():
            return

        if not os.path.exists(self.piper_path):
            raise FileNotFoundError(f"Piper binary not found: {self.piper_path}")
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Piper model not found: {self.model_path}")

        # Choose mode: IPA phoneme or normal text
        ipa_json = self._try_get_ipa_json(text)
        if ipa_json:
            input_data = ipa_json.encode("utf-8")
            use_phoneme_mode = True
        else:
            processed_text = self._preprocess_text(text)
            input_data = processed_text.encode("utf-8")
            use_phoneme_mode = False

        # Temp file for Piper output
        out_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name

        # 🧠 Run Piper
        start_time = time.time()
        cmd = [
            self.piper_path,
            "--model", self.model_path,
            "--output_file", out_wav
        ]
        if use_phoneme_mode:
            cmd.append("--phoneme-input")

        subprocess.run(
            cmd,
            input=input_data,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        gen_time = time.time() - start_time

        # 🔊 Play using PowerShell's SoundPlayer (no UI)
        subprocess.run(
            [
                "powershell",
                "-c",
                f"(New-Object Media.SoundPlayer '{out_wav}').PlaySync();"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        print(f"\033[92m[TTS] ⏱️ Generated & played in {gen_time:.2f}s\033[0m")

        # 🧼 Clean up the temp file
        if os.path.exists(out_wav):
            os.remove(out_wav)
