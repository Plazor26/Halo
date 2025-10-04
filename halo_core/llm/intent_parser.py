import json
import re
import traceback
from pathlib import Path

class IntentParser:
    """
    Intent Parser:
    - Handles quick regex-based detection for special cases (like volume)
    - Validates & cleans intents JSON returned by the LLM
    - Uses external action_map.json for validation
    - Does NOT call the LLM itself anymore (that happens in main.py)
    """

    def __init__(self, debug=False):
        self.debug = debug
        self.action_map = self._load_action_map()

    def _load_action_map(self):
        """
        Load action_map.json from the skills directory.
        """
        action_map_path = Path(__file__).resolve().parent.parent / "skills" / "action_map.json"
        try:
            with open(action_map_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[IntentParser] ⚠️ Failed to load action_map.json: {e}")
            return {}

    def _handle_special_cases(self, text):
        """
        Handle special cases that are easy to regex without LLM.
        e.g. volume adjustments like "set volume to 50%"
        """
        # 🔊 Volume: "set volume to X%", "volume 70", "increase volume to 30"
        volume_match = re.search(r"volume\s*(to)?\s*(\d{1,3})\s*%?", text.lower())
        if volume_match:
            vol = int(volume_match.group(2))
            vol = max(0, min(100, vol))
            return {"intents": [{"action": "set_volume", "target": vol}]}

        return None

    def validate_intents(self, raw_json_str):
        """
        Validates that a given string is valid intents JSON.
        Returns {"intents": [...]} or {"intents": []} on failure.
        """
        try:
            data = json.loads(raw_json_str)
            if self.debug:
                print("[IntentParser Raw JSON]", data)

            if not isinstance(data, dict) or "intents" not in data:
                return {"intents": []}

            intents = data["intents"]
            if not isinstance(intents, list):
                return {"intents": []}

            # 🧼 Clean up & filter by action_map
            clean_intents = []
            for intent in intents:
                if not isinstance(intent, dict):
                    continue

                action = intent.get("action")
                target = intent.get("target")

                if action and action in self.action_map:
                    clean_intents.append({"action": action, "target": target})
                else:
                    if self.debug:
                        print(f"[IntentParser] ⚠️ Ignored unknown action: {action}")

            return {"intents": clean_intents}

        except Exception as e:
            print("[IntentParser] ❌ Failed to parse or validate JSON:")
            print(raw_json_str)
            print(f"[Error] {e}")
            traceback.print_exc()
            return {"intents": []}

    def parse(self, text_or_json):
        """
        Entry point:
        - If input is natural language, check special cases.
        - If input is JSON (string), validate it.
        - If dict, also validate structure.
        """
        # 1️⃣ Special cases first
        if isinstance(text_or_json, str):
            special = self._handle_special_cases(text_or_json)
            if special:
                return special

            # Might be a JSON string (from LLM)
            if text_or_json.strip().startswith("{"):
                return self.validate_intents(text_or_json)

        # 2️⃣ If already a dict (from LLM), validate structure
        if isinstance(text_or_json, dict):
            return self.validate_intents(json.dumps(text_or_json))

        return {"intents": []}
