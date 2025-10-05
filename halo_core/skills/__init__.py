# halo_core/skills/__init__.py
from __future__ import annotations
import importlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

ACTION_MAP_PATH = Path(__file__).resolve().parent / "action_map.json"
if not ACTION_MAP_PATH.exists():
    raise FileNotFoundError(f"⚠️ action_map.json not found at {ACTION_MAP_PATH}")

with open(ACTION_MAP_PATH, "r", encoding="utf-8") as f:
    ACTION_MAP: Dict[str, Any] = json.load(f)


def _resolve_action_entry(action: str, entry: Any) -> Optional[Tuple[str, str]]:
    """
    Normalize different mapping styles into (module_name, func_name).

    Supported shapes in action_map.json:
      - ["module_name", "function_name"]
      - {"module": "module_name", "function": "function_name"}
      - "module_name.function_name"   (string dotted path)
    """
    if isinstance(entry, list) and len(entry) == 2:
        module_name, func_name = entry
        return str(module_name), str(func_name)

    if isinstance(entry, dict):
        module_name = entry.get("module")
        func_name = entry.get("function")
        if module_name and func_name:
            return str(module_name), str(func_name)

    if isinstance(entry, str) and "." in entry:
        module_name, func_name = entry.rsplit(".", 1)
        return module_name, func_name

    # Unrecognized shape
    print(f"[Skills] invalid map entry for '{action}': {entry!r}")
    return None


def _import_skill(module_name: str, func_name: str):
    """
    Import halo_core.skills.<module_name> and fetch <func_name>.
    """
    module = importlib.import_module(f"halo_core.skills.{module_name}")
    func = getattr(module, func_name, None)
    if not callable(func):
        print(f"[Skills] function '{func_name}' not found in module '{module_name}'.")
        return None
    return func


def _postprocess_result(action: str, result: Any) -> Optional[str]:
    """
    Convert a skill's return into a human-friendly string for TTS/HUD/logs.

    Conventions:
      - If the skill returns a dict with 'summary', prefer that for speaking.
      - If it returns a plain string, use it as-is.
      - Otherwise, return None (silent).
    """
    if result is None:
        return None

    if isinstance(result, dict):
        # Prefer concise 'summary'
        summary = result.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()

        # Fallback: compact dump without being noisy
        try:
            compact = json.dumps(result, ensure_ascii=False)
            return compact
        except Exception:
            return str(result)

    if isinstance(result, (str, bytes)):
        try:
            return result.decode("utf-8") if isinstance(result, bytes) else result
        except Exception:
            return str(result)

    # Last resort
    try:
        return json.dumps(result, ensure_ascii=False)
    except Exception:
        return str(result)


def execute_intents(intents: List[Dict[str, Any]]) -> List[str]:
    """
    Dispatch parsed intents to their respective skill functions.

    Returns:
        List[str] – human-friendly messages produced by skills,
        suitable for logging, HUD, or TTS (caller decides).
    """
    responses: List[str] = []
    if not intents:
        return responses

    for intent in intents:
        action = intent.get("action")
        target = intent.get("target")

        print(f"[Skills] dispatch → action={action} target={target}")

        if not action:
            print("[Skills] missing 'action' in intent, skipping.")
            continue

        entry = ACTION_MAP.get(action)
        if not entry:
            print(f"[Skills] unknown action '{action}', skipping.")
            continue

        resolved = _resolve_action_entry(action, entry)
        if not resolved:
            # Already logged invalid shape
            continue

        module_name, func_name = resolved

        try:
            func = _import_skill(module_name, func_name)
            if not func:
                continue

            # Call with or without target depending on signature tolerance
            try:
                result = func(target) if target is not None else func()
            except TypeError:
                # Skill might not accept args
                result = func()

            msg = _postprocess_result(action, result)
            if msg:
                responses.append(msg)

        except Exception as e:
            print(f"[Skills] error executing '{action}': {e}")

    return responses
