# tests/intent_parser_test.py
from halo_core.llm.intent_parser import IntentParser

if __name__ == "__main__":
    parser = IntentParser(model="gemma3:4b")
    text = "Open Chrome and mute the system"
    result = parser.parse(text)
    print("[Parsed Intents]")
    print(result)
