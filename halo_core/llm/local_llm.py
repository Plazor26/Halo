# halo_core/llm/local_llm.py
import requests
import json

class LocalLLM:
    def __init__(self, model="gemma3:4b", api_url="http://localhost:11434/api/generate"):
        self.model = model
        self.api_url = api_url

    def generate(self, prompt: str, stream: bool = False) -> str:
        """
        Generate a response from the local Ollama model.

        - stream=False → returns the full text as a string (default)
        - stream=True  → streams chunks and returns concatenated string at the end
        """
        if not prompt or not prompt.strip():
            return ""

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream
        }

        try:
            # 🟢 Non-streaming: standard full generation
            if not stream:
                resp = requests.post(self.api_url, json=payload, timeout=60)
                resp.raise_for_status()
                data = resp.json()
                return data.get("response", "").strip()

            # 🟡 Streaming: collect and merge chunks
            with requests.post(self.api_url, json=payload, stream=True, timeout=60) as resp:
                resp.raise_for_status()
                chunks = []
                for line in resp.iter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        chunk = data.get("response", "")
                        if chunk:
                            chunks.append(chunk)
                    except json.JSONDecodeError:
                        # Ignore malformed partial lines gracefully
                        continue
                return "".join(chunks).strip()

        except requests.exceptions.RequestException as e:
            print(f"[LocalLLM] ❌ Network or API error: {e}")
            return "(...ugh, my brain froze. Try again?)"

        except Exception as e:
            print(f"[LocalLLM] ❌ Unexpected error: {e}")
            return "(Something went wrong with my thoughts...)"
