# halo_core/llm/local_llm.py
import requests
import json

class LocalLLM:
    def __init__(self, model="gemma3:4b", api_url="http://localhost:11434/api/generate"):
        self.model = model
        self.api_url = api_url

    def generate(self, prompt, stream=False):
        """
        Generate a response from the local Ollama model.
        - If stream=False → returns the full string.
        - If stream=True → yields chunks as they arrive.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream
        }

        # 🟡 Non-streaming mode: simple string return
        if not stream:
            resp = requests.post(self.api_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "").strip()

        # 🟡 Streaming mode: collect chunks, then return joined string
        # (because your main expects a string, not a generator)
        resp = requests.post(self.api_url, json=payload, stream=True)
        resp.raise_for_status()

        chunks = []
        for line in resp.iter_lines():
            if line:
                data = json.loads(line)
                chunk = data.get("response", "")
                if chunk:
                    chunks.append(chunk)
        resp.close()
        return "".join(chunks).strip()
