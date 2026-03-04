"""LLM API interface — OpenAI-compatible chat completions."""

import httpx
from .config import Config


def chat(messages: list[dict], config: Config, system: str | None = None,
         model_override: str | None = None, api_base_override: str | None = None,
         api_key_override: str | None = None) -> str:
    """Synchronous chat completion. Use chat_async in async contexts."""
    if system:
        messages = [{"role": "system", "content": system}] + messages

    model = model_override or config.model
    api_base = api_base_override or config.api_base
    api_key = api_key_override or config.api_key

    resp = httpx.post(
        f"{api_base}/chat/completions",
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 4096,
        },
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=300.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


async def chat_async(messages: list[dict], config: Config, system: str | None = None,
                     on_token: callable = None,
                     model_override: str | None = None, api_base_override: str | None = None,
                     api_key_override: str | None = None) -> str:
    """Async chat completion — non-blocking, for use inside TUI event loop.

    If on_token is provided, streams tokens and calls on_token(chunk_text) for each.
    Returns the full response text either way.
    """
    if system:
        messages = [{"role": "system", "content": system}] + messages

    model = model_override or config.model
    api_base = api_base_override or config.api_base
    api_key = api_key_override or config.api_key

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 4096,
    }

    if on_token:
        payload["stream"] = True
        full_response = []
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{api_base}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=300.0,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    import json
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        text = delta.get("content", "")
                        if text:
                            full_response.append(text)
                            on_token(text)
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
        return "".join(full_response)
    else:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{api_base}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=300.0,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
