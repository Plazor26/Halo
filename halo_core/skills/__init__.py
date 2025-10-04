import importlib
import json
import os

# Load action map dynamically from JSON
ACTION_MAP_PATH = os.path.join(os.path.dirname(__file__), "action_map.json")
with open(ACTION_MAP_PATH, "r", encoding="utf-8") as f:
    ACTION_MAP = json.load(f)

def execute_intents(intents: list):
    """
    Dispatch parsed intents to their respective skill functions.
    Each skill returns a string (Halo's tsundere response),
    which is collected and returned as a list.
    """
    responses = []

    if not intents:
        return []

    for intent in intents:
        action = intent.get("action")
        target = intent.get("target")

        if not action or action not in ACTION_MAP:
            responses.append(f"Hmph, I don't know how to '{action}' yet.")
            continue

        module_name, func_name = ACTION_MAP[action]

        try:
            module = importlib.import_module(f"halo_core.skills.{module_name}")
            func = getattr(module, func_name, None)
            if not func:
                responses.append(f"Ugh, the '{action}' skill is missing... who forgot to write it?!")
                continue

            try:
                result = func(target) if target is not None else func()
            except TypeError:
                result = func()

            if result:
                responses.append(result)

        except Exception as e:
            responses.append(f"Ugh… something went wrong with '{action}': {e}")

    return responses
