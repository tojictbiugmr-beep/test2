import os
import requests

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
MODEL = "groq/compound-mini"

class _Message:
    def __init__(self, content):
        self.content = content

class _Choice:
    def __init__(self, content):
        self.message = _Message(content)

class _Response:
    def __init__(self, content):
        self.choices = [_Choice(content)]

class _Completions:
    def create(self, model=None, messages=None, max_tokens=500, temperature=0.7, **kwargs):
        payload = {
            "model": model or MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        resp = requests.post(
            f"{GROQ_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return _Response(data["choices"][0]["message"]["content"])

class _Chat:
    def __init__(self):
        self.completions = _Completions()

class OpenAICompat:
    def __init__(self):
        self.chat = _Chat()

client = OpenAICompat()
