"""LLM API interface — OpenAI-compatible chat completions."""

import httpx
from .config import Config


def chat(messages: list[dict], config: Config, system: str | None = None) -> str:
    """Synchronous chat completion. Use chat_async in async contexts."""
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
        timeout=300.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


async def chat_async(messages: list[dict], config: Config, system: str | None = None) -> str:
    """Async chat completion — non-blocking, for use inside TUI event loop."""
    if system:
        messages = [{"role": "system", "content": system}] + messages

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{config.api_base}/chat/completions",
            json={
                "model": config.model,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 4096,
            },
            headers={"Authorization": f"Bearer {config.api_key}"},
            timeout=300.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
