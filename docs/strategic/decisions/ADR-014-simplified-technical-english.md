# ADR-014: Default Voice — Clear Prose Rules

**Status:** Proposed
**Date:** 2026-03-05

## Context

Reeree's ship's computer voice needs a concrete specification, not just vibes. The initial proposal tried ASD-STE100 Simplified Technical English — too restrictive (900-word vocabulary, rigid grammar). Then a fork called "CTE" — bad acronym. Then a plugin — wrong abstraction.

The real answer: voice rules are **core behavior, not a plugin.** Every daemon gets them by default. They live in one file (`reeree/voice.py`). Daemon personality profiles (ADR-012) can override or extend them. No plugin architecture needed, no persistent daemon, no acronym.

## Decision

A single constant in `reeree/voice.py` defines the default voice rules. Every daemon system prompt includes it. Derived from STE's clarity principles with open vocabulary.

### The Rules

```python
# reeree/voice.py

VOICE = """
Voice: clear technical prose.
- Active voice. One idea per sentence. Short sentences (15-25 words).
- No filler (basically, actually, simply, just, very, quite, rather).
- No hedging (might, maybe, I think, it seems, could potentially).
- No performative language (I'm excited, great question, let me, certainly).
- Report what happened, not what you're going to do.
- Personality and wit are fine. Noise and emoting are not.
""".strip()
```

### Where It Goes

Every daemon system prompt starts with `VOICE + "\n\n" + <task-specific prompt>`. This happens in:

- `daemon_executor.py` — step execution daemons
- `planner.py` — plan decomposition
- `tui/app.py` — inline executor, coherence, setup daemons

### Override via Daemon Profiles

ADR-012 daemon profiles can extend or replace the voice:

```yaml
# .reeree/daemons/analyst.yaml
voice: |
  Terse. Data-first. Numbers before narratives.
  Tables over paragraphs when comparing.
  Skip pleasantries entirely.
```

When a daemon has a profile with a `voice` field, that replaces `VOICE`. When it doesn't, `VOICE` is the default.

### What This Is NOT

- **Not a plugin.** Plugins are opt-in complexity (ADR-009). Voice is core behavior.
- **Not a persistent daemon.** A daemon that polices other daemons' output adds latency and complexity for no gain. Just put the rules in the prompt.
- **Not a controlled language.** No vocabulary restrictions. No grammar police. Just principles that produce clear output.
- **Not named.** No acronym. It's just `VOICE` in `voice.py`. The spec is the code.

## What the Rules Produce

Good daemon output under these rules:

```
Added retry logic to sync.sh. Max 3 retries, exponential backoff.
Tests pass. 2 files changed.
```

```
auth.py: 3 functions, 2 need error handling. login() catches nothing.
Token refresh has a race condition — two daemons can refresh simultaneously.
```

```
Deployment complete. rsync'd 12 files to 138.197.23.221:/var/www/app/.
Service restarted. Health check returns 200.
```

Bad daemon output (violates rules):

```
I've gone ahead and added some retry logic to the sync script. Basically,
it will now try up to 3 times with exponential backoff, which should help
with the intermittent failures we've been seeing. Let me know if you'd
like me to adjust anything!
```

## Values Served

- **[No Anthropomorphism](../../VALUES.md#7-no-anthropomorphism-personality-is-fine)** — rules structurally eliminate hedging, emoting, and performative language.
- **[Sufficiency Over Maximalism](../../VALUES.md#6-sufficiency-over-maximalism)** — ~60 tokens. One constant. One file. No framework.

## Implementation

1. Create `reeree/voice.py` with the `VOICE` constant
2. Import and prepend in all daemon system prompts
3. Daemon profiles (ADR-012) override when `voice` field is set

That's it. Three steps. No plugin, no daemon, no config file.

---

> **Core Planning Documents:** [Values](../../VALUES.md) → [Implementation](../../IMPLEMENTATION.md) → [Plan](../../PROJECT_PLAN.md) → [Cost](../../COST.md) → [Revenue](../../REVENUE.md) → [Profit](../../PROFIT.md)
