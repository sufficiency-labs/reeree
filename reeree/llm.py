"""LLM API interface — OpenAI-compatible chat completions."""

import httpx
from .config import Config


def chat(messages: list[dict], config: Config, system: str | None = None) -> str:
    """Send a chat completion request and return the response text.

    Uses the OpenAI-compatible /v1/chat/completions endpoint,
    which works with ollama, litellm, vllm, and any cloud API.
    """
    if system:
        messages = [{"role": "system", "content": system}] + messages

    resp = httpx.post(
        f"{config.api_base}/chat/completions",
        json={
            "model": config.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 4096,
        },
        headers={"Authorization": f"Bearer {config.api_key}"},
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def chat_stream(messages: list[dict], config: Config, system: str | None = None):
    """Stream a chat completion, yielding text chunks.

    Yields partial content strings as they arrive.
    """
    if system:
        messages = [{"role": "system", "content": system}] + messages

    with httpx.stream(
        "POST",
        f"{config.api_base}/chat/completions",
        json={
            "model": config.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 4096,
            "stream": True,
        },
        headers={"Authorization": f"Bearer {config.api_key}"},
        timeout=120.0,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                import json
                chunk = json.loads(line[6:])
                delta = chunk["choices"][0].get("delta", {})
                if "content" in delta:
                    yield delta["content"]
