# ADR-014: Simplified Technical English as Default Voice Spec

**Status:** Proposed
**Date:** 2026-03-05

## Context

Reeree's ship's computer voice needs a concrete specification, not just vibes. ASD-STE100 Simplified Technical English is a controlled natural language standard originally designed for aerospace maintenance manuals. Its rules produce exactly the kind of output reeree wants: clear, direct, unambiguous, no filler.

STE's core constraints:
- One word, one meaning (no synonyms — pick "start", never "begin/commence/initiate")
- Max 25 words per procedural sentence, 20 per step
- Active voice only
- No present perfect tense
- Approved vocabulary (~900 words) plus domain-specific technical terms
- No unnecessary adjectives or adverbs

This maps directly to the ship's computer voice: direct, informational, no hedging.

## Decision

STE rules form the **default expressive language constraint** for all daemon output. Implemented as the first reeree plugin (`reeree-ste`), which:

1. **Injects STE rules into every daemon system prompt** — a brief summary of the key constraints, not the full 53-rule spec
2. **Allows project-specific technical terms** — the STE dictionary is extended with terms from the project (function names, tool names, domain vocabulary)
3. **Is the default plugin** — enabled by default, can be disabled per project

### STE Rules Summary for System Prompts

The plugin prepends approximately this to every daemon system prompt:

```
Output constraints (Simplified Technical English):
- Max 25 words per sentence. Max 20 words per procedural step.
- Active voice. Present tense. No present perfect.
- One word, one meaning. Use "start" not "begin/commence/initiate".
- No filler: remove "basically", "actually", "essentially", "simply".
- No hedging: remove "might", "perhaps", "I think", "it seems".
- Approved verbs for actions: do, make, put, get, go, set, run, test, check, read, write, find, show, give, keep, let, move, open, close, turn, add, cut, hold.
- Report what happened, not what you're "going to" do.
- Technical terms from this project are permitted as-is.
```

### Plugin Architecture

```python
# reeree_ste/plugin.py
class STEPlugin(ReereePlugin):
    name = "reeree-ste"

    def on_daemon_prompt(self, prompt: str, daemon: Daemon) -> str:
        """Prepend STE constraints to daemon system prompt."""
        return STE_RULES + "\n\n" + prompt

    def on_plan_loaded(self, plan: Plan) -> None:
        """Extract technical terms from plan for STE dictionary."""
        # Scan step descriptions for project-specific terms
        pass
```

### Configurable strictness

```yaml
# .reeree/plugins/ste.yaml
enabled: true
strictness: standard  # relaxed | standard | strict
custom_terms:
  - pytest
  - daemon
  - systemd
  - rsync
```

- **relaxed**: Only no-hedging and no-filler rules. Sentence length unconstrained.
- **standard**: Full STE rules. Technical terms auto-discovered from project.
- **strict**: Full STE rules. Manual term approval required.

## Values Served

- **[No Anthropomorphism](../../VALUES.md#7-no-anthropomorphism-personality-is-fine)** — STE structurally prevents hedging, emoting, and simulated cognition. The vocabulary constraints make it physically difficult to write "I think" or "I'm excited."
- **[Sufficiency Over Maximalism](../../VALUES.md#6-sufficiency-over-maximalism)** — STE was designed for non-native English speakers maintaining aircraft. If it works for them, it works for daemon output. No wasted tokens.
- **[Plan Is the Interface](../../VALUES.md#2-plan-is-the-interface)** — STE makes plan step descriptions clear and actionable. "Add retry logic to sync.sh" not "We should consider implementing a retry mechanism."

## Alternatives Considered

| Option | Verdict | Why |
|--------|---------|-----|
| Ad-hoc voice guidelines in system prompts | Current state | Works but inconsistent. Different prompts say different things. |
| Full STE spec (53 rules, 900-word dictionary) | Too heavy | Adds ~2000 tokens to every prompt. Models don't need the full spec. |
| Custom controlled language | Unnecessary | STE already exists and is well-specified. Don't reinvent it. |
| Plugin (proposed) | Accepted | Configurable, disable-able, extensible with project terms. |

## Implementation Path

1. Create `reeree-ste` plugin package with STE rules summary
2. Add `on_daemon_prompt` hook to plugin interface (ADR-009)
3. Register as default plugin in setup wizard
4. Auto-discover technical terms from project files
5. Add `:ste` command to toggle strictness

---

> **Core Planning Documents:** [Values](../../VALUES.md) → [Implementation](../../IMPLEMENTATION.md) → [Plan](../../PROJECT_PLAN.md) → [Cost](../../COST.md) → [Revenue](../../REVENUE.md) → [Profit](../../PROFIT.md)
