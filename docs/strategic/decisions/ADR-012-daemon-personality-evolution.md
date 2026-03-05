# ADR-012: Daemon Personality Evolution

**Status:** Proposed
**Date:** 2026-03-05

## Context

Reeree's daemons are currently stateless — each spawn is a fresh process with a generic system prompt. The user wants daemons that develop sub-personalities over time through interaction, shaped by the tasks they execute and the corrections they receive. This is directly inspired by the daimones system in Walter Jon Williams' *Aristoi*, but grounded in practical utility rather than science fiction.

Key design constraint from the user: "useful version first, not scifi." The personalities should emerge from work patterns, not be pre-designed archetypes.

## The Aristoi Model (Reference)

In the novel, Aristoi cultivate named daimones — internal sub-personalities specialized for different cognitive domains. Each daimon has:
- A distinct voice and communication style
- Specialized domain knowledge
- The ability to operate independently on assigned tasks
- Subordination to the primary personality's governance

The critical property: **the user creates, shapes, and controls the daimones.** They are products of the user's interactions and training, not autonomous entities.

## Decision

Daemon personalities are **emergent artifacts of accumulated interaction**, stored as editable YAML profiles that the user owns and controls.

### How Personalities Develop

1. **Accumulation**: Each daemon kind (EXECUTOR, COHERENCE, STATE, etc.) accumulates a profile from completed tasks:
   - Corrections the user made ("too verbose" → learns terse reporting)
   - Domain patterns ("always uses pytest" → learns project conventions)
   - Successful approaches (what worked gets reinforced)
   - Failed approaches (what didn't gets noted)

2. **Profile storage**: `.reeree/daemons/<name>.yaml` — plain text, user-editable:
   ```yaml
   name: analyst
   kind: executor
   voice: terse, data-first, no hedging
   learned:
     - user prefers single-line log output
     - always run tests after edits
     - never use emoji in output
   domain_context:
     - pytest patterns for this project
     - deployment is rsync to prod droplet
   corrections:
     - "too verbose" (2026-03-01)
     - "don't anthropomorphize" (2026-03-04)
   style_examples:
     - "done d3 abc1234 (12.3s) — added retry logic"
     - "3 files changed, tests pass"
   ```

3. **Profile injection**: When a daemon spawns, its profile YAML is prepended to the system prompt. The LLM receives the accumulated personality as context.

4. **User control**: The user can:
   - Edit any profile directly (it's YAML on disk)
   - Reset a profile (delete the file)
   - Fork a profile (copy and modify)
   - Name daemons (`:name d3 analyst`)
   - Merge profiles (combine learnings from two daemons)

### What Develops vs. What Doesn't

**Develops over time:**
- Communication style (voice, verbosity, formatting preferences)
- Domain knowledge (project conventions, tool preferences, deployment targets)
- Task approach patterns (test-first vs code-first, planning depth)
- Correction history (what the user pushed back on)

**Does NOT develop:**
- Goals or motivations (daemons don't "want" things)
- Autonomy scope (that's set by the user, not learned)
- Emotional responses (no simulated feelings)
- Self-initiated behavior (daemons don't decide to change themselves)

### Named Daemons vs. Daemon Kinds

- **DaemonKind** (EXECUTOR, COHERENCE, etc.) defines the *role* — what the daemon does
- **Daemon name** (analyst, builder, reviewer) defines the *personality* — how it does it
- A single kind can have multiple named personalities
- Default: unnamed daemons use a base profile per kind
- Named daemons accumulate their own profile over time

### Practical Example

```
# User works on a project for a week. The executor daemon:
# - Gets corrected 3 times about log verbosity
# - Learns the project uses pytest, not unittest
# - Discovers the user prefers rsync deploys over scp
# - Notes the user always wants tests run after code changes

# This accumulates in .reeree/daemons/default-executor.yaml
# Next session, the executor daemon is pre-loaded with these preferences
# The user never had to configure anything — it emerged from work
```

### Implementation Path

1. **Phase 1 (now)**: Profile YAML format + manual creation/editing
2. **Phase 2**: Automatic profile accumulation from user corrections
3. **Phase 3**: Named daemons with persistent identities across sessions
4. **Phase 4**: Profile forking, merging, and sharing between projects

## Values Served

- **[Delegated Agency](../../VALUES.md#1-delegated-agency)** — profiles are the user's creation, not the daemon's. The user controls what develops.
- **[No Hidden State](../../VALUES.md#red-lines)** — profiles are YAML on disk, readable and editable by any text editor.
- **[No Anthropomorphism](../../VALUES.md#7-no-anthropomorphism-personality-is-fine)** — personality (voice, style, learned conventions) without simulated cognition or emotion.
- **[Look Before You Ask](../../VALUES.md#8-look-before-you-ask)** — accumulated domain knowledge means daemons ask fewer questions over time.

## Alternatives Considered

| Option | Verdict | Why |
|--------|---------|-----|
| Pre-designed archetypes (Analyst, Builder, etc.) | Rejected | Sci-fi cosplay, not useful. Personalities should emerge from work. |
| Hidden ML-trained personality models | Rejected | Violates no-hidden-state. User can't inspect or edit. |
| Per-session personality (no persistence) | Rejected | Loses accumulated learning. User repeats corrections. |
| Fully autonomous self-modification | Rejected | Violates delegated agency. User must control what develops. |

## Consequences

- Daemon profiles add ~500 tokens to system prompts (acceptable for 32K models)
- Profile accumulation requires parsing user corrections from chat history
- Named daemons need stable identifiers across sessions (ties to daemon persistence)
- Profile sharing between projects is possible but optional (`.reeree/daemons/` is per-project by default)

---

> **Core Planning Documents:** [Values](../../VALUES.md) → [Implementation](../../IMPLEMENTATION.md) → [Plan](../../PROJECT_PLAN.md) → [Cost](../../COST.md) → [Revenue](../../REVENUE.md) → [Profit](../../PROFIT.md)
