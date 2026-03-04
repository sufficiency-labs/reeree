# ADR-004: OpenAI-Compatible API Interface

**Status:** Accepted
**Date:** 2026-02-15

## Context

Must work with any LLM provider, local or cloud. Users should be able to use ollama on localhost, together.ai, OpenRouter, or any other provider without code changes.

## Decision

All LLM calls go through OpenAI-compatible `/v1/chat/completions` endpoint.

## Values Served

- **[Sufficiency Over Maximalism](../../VALUES.md#6-sufficiency-over-maximalism)** — Works with $0 local models (ollama), doesn't require expensive commercial APIs
- **No Lock-in** (Red Line) — Any OpenAI-compatible API works

## Rationale

ollama, litellm, vllm, and every cloud provider support the OpenAI chat completions format. One interface covers everything. Users bring their own API keys and endpoints.

## Alternatives Considered

| Option | Verdict | Why |
|--------|---------|-----|
| Native provider SDKs | Rejected | Each is different, creates lock-in |
| LangChain | Rejected | Massive dependency, over-abstracted |

## Consequences

- Features that require provider-specific APIs (tool use, structured output) need adapter patterns or degrade gracefully
- Model-specific quirks (token limits, response formatting) handled in configuration, not code

## Implementation

- LLM interface: `reeree/llm.py` — `chat_async()` with httpx, model/API overrides
- Config: `reeree/config.py` — `api_base`, `model`, `api_key` fields
- Router: `reeree/router.py` — multi-model routing with per-tier API settings

---

> **Core Planning Documents:** [Values](../../VALUES.md) → [Implementation](../../IMPLEMENTATION.md) → [Plan](../../PROJECT_PLAN.md) → [Cost](../../COST.md) → [Revenue](../../REVENUE.md) → [Profit](../../PROFIT.md)
