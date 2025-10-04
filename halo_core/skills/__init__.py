import importlib

# 🗺️ Central action-to-skill mapping
ACTION_MAP = {
    # 🖥️ System control
    "shutdown": ("system_control", "shutdown"),
    "restart": ("system_control", "restart"),
    "sleep": ("system_control", "sleep"),
    "mute_system": ("system_control", "mute_system"),
    "unmute_system": ("system_control", "unmute_system"),
    "set_volume": ("system_control", "set_volume"),
    "close_all_apps": ("system_control", "close_all_apps"),
    "open_task_manager": ("system_control", "open_task_manager"),
    "open_website": ("system_control", "open_website"),
    "play_pause_media": ("system_control", "play_pause_media"),

    # 🪄 Apps
    "open_app": ("apps", "open_app"),
    "close_app": ("apps", "close_app"),

    # ⏰ Automation / future
    "schedule_task": ("automation", "schedule_task"),

    # 📊 Monitoring
    "check_status": ("monitoring", "check_status"),

    # 🔔 Notifications
    "notify": ("notifications", "send_notification"),
}


def execute_intents(intents: list):
    """
    Dispatch parsed intents to their respective skill functions.
    Each skill returns a string (Halo's tsundere response),
    which is collected and returned as a list.
    """
    responses = []

    if not intents:
        return ["Hmph, you didn't even *tell* me what to do. Baka."]

    for intent in intents:
        action = intent.get("action")
        target = intent.get("target")

        if not action:
            responses.append("You forgot to give me an action… how typical 🙄")
            continue

        module_name, func_name = ACTION_MAP.get(action, (None, None))
        if not module_name:
            responses.append(f"Hmph, I don't know how to '{action}' yet. Maybe teach me? 😤")
            continue

        try:
            # 📦 Import the module dynamically
            module = importlib.import_module(f"halo_core.skills.{module_name}")

            # 🧭 Get the function by name
            func = getattr(module, func_name, None)
            if not func:
                responses.append(f"Ugh, the '{action}' skill is missing... who forgot to write it?!")
                continue

            # 🛠️ Call with or without target (safe)
            try:
                result = func(target) if target is not None else func()
            except TypeError:
                # Function likely takes no args
                result = func()

            # ✨ Collect the response
            if result:
                responses.append(result)

        except Exception as e:
            responses.append(f"Ugh… something went wrong with '{action}': {e}")

    return responses
