# tests/llm_test.py
from halo_core.llm.local_llm import LocalLLM

if __name__ == "__main__":
    llm = LocalLLM(model="gemma3:4b")
    print("[LLM Stream] → ", end="", flush=True)
    for chunk in llm.generate("Hello, who are you?", stream=True):
        print(chunk, end="", flush=True)
    print()
