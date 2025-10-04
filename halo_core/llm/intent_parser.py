import json
import re
import traceback
from halo_core.llm.local_llm import LocalLLM

class IntentParser:
    def __init__(self, model="gemma3:4b", llm=None, debug=False):
        self.llm = llm if llm is not None else LocalLLM(model=model)
        self.debug = debug  # 👈 THIS was missing

        self.system_prompt = (
            "You are Halo's intent parser. "
            "Your job is to convert natural language commands into structured JSON objects.\n\n"
            "RULES:\n"
            " - Return ONLY valid JSON. No explanations, no extra text.\n"
            " - Do NOT wrap JSON in Markdown fences.\n"
            " - JSON format:\n"
            "{\n"
            "  \"intents\": [\n"
            "    {\"action\": \"<action>\", \"target\": \"<optional_target>\"}\n"
            "  ]\n"
            "}\n"
            " - Examples of actions: open_app, close_app, mute_system, unmute_system, shutdown, restart, search_web, play_media, stop_media, schedule_task\n"
            " - Targets are things like 'chrome', 'spotify', 'notepad', file paths, or search queries.\n"
            " - If multiple commands are given, include multiple objects in the intents array.\n"
            " - If unsure, guess the closest reasonable action.\n"
        )



    def parse(self, text):
        # 1️⃣ Volume command pattern
        volume_match = re.search(r"volume\s*(to)?\s*(\d{1,3})\s*%?", text.lower())
        if volume_match:
            vol = int(volume_match.group(2))
            return {"intents": [{"action": "set_volume", "target": vol}]}
        # 2️⃣ Fallback to LLM
        """Convert natural language into structured intents via local LLM."""
        full_prompt = f"{self.system_prompt}\nUser command: \"{text}\"\nJSON:\n"

        # Collect streaming chunks
        chunks = []
        try:
            for c in self.llm.generate(full_prompt, stream=True):
                chunks.append(c)
        except Exception as e:
            print(f"[IntentParser] ❌ LLM streaming failed: {e}")
            traceback.print_exc()
            return {"intents": []}

        response = "".join(chunks).strip()

        # Strip possible markdown fences or language hints
        response = re.sub(r"^```(?:json)?\s*", "", response)
        response = re.sub(r"\s*```$", "", response)

        if self.debug:
            print("[IntentParser Raw LLM]", response)

        # Validate and parse JSON
        try:
            data = json.loads(response)
            # Sanity check: ensure "intents" is at least present
            if "intents" not in data or not isinstance(data["intents"], list):
                raise ValueError("Missing or malformed 'intents' key")
            return data
        except Exception as e:
            print("[IntentParser] ❌ Failed to parse JSON from LLM response:")
            print(response)
            print(f"[Error] {e}")
            return {"intents": []}
