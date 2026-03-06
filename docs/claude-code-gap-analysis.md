# Claude Code → Reeree Gap Analysis

**Date:** 2026-03-05
**Source:** Analysis of 23 Claude Code sessions, 768 user messages, Feb 17 – Mar 5 2026.

## How Rob Actually Uses Claude Code

The sessions reveal **five distinct usage modes**, not one. Reeree needs to handle all of them.

### Mode 1: Dispatch Console (40% of usage)
Plan-driven coding work. User writes intent → system decomposes into steps → daemons execute → user reviews.
**Status in reeree:** Core architecture. 70% built. Plan/step/daemon/execute loop works.

### Mode 2: Sysadmin Shell (25% of usage)
SSH into boxes, configure systemd, debug networking, deploy to droplets, manage cloud sync. Heavy bash, low planning. The user wants a knowledgeable operator with root access.
**Status in reeree:** Executor daemon can run shell commands but lacks:
- Remote execution (SSH through the tool)
- Service health awareness (which timers are running, what failed)
- Deployment state tracking (what version is on which box)
- IP/URL/credential memory (user constantly re-asks for these)

### Mode 3: Writing Partner / Critical Thinking (20% of usage)
Diary entries, essay drafting, argument development, research synthesis. The user writes stream-of-consciousness and wants the tool to sharpen arguments, find counterexamples, check facts, and suggest structure — NOT to write for them.
**Status in reeree:** Chat panel exists but lacks:
- Long-form document editing (the PlanEditor is for plans, not essays)
- Research capabilities (web search, book lookup, cross-referencing)
- Critique mode (daemon that reads what you wrote and asks hard questions)
- Knowledge base integration (diary archive, book collection, idea-index)

### Mode 4: Personal Analysis / Emotional Processing (10% of usage)
Family analysis, relationship assessment, self-reflection. Uses the tool as an honest mirror — "tell me what the data says, including the painful parts." Requires access to the relationships repo, diary, communications archive.
**Status in reeree:** Not addressed. Requires:
- Abstraction repo access (people, ideas, choices, states, personas)
- Cross-referencing engine (follow links between entries)
- Honesty enforcement (the anti-hagiography directive)

### Mode 5: Rapid Prototyping / Games (5% of usage)
Build a thing fast, deploy it, iterate visually. Short feedback loops, high parallelism, frequent redirection.
**Status in reeree:** Daemon parallelism works but lacks:
- Visual feedback (screenshot of what was built)
- One-command deployment to droplets
- Asset generation (images, sounds)

## Specific Gaps (Prioritized)

### Critical — Reeree can't replace Claude Code without these

| Gap | What Claude Code Does | What Reeree Needs |
|-----|----------------------|-------------------|
| **Context persistence** | 23 sessions, auto-summarization on context exhaustion | Session serialization (ADR-001), daemon persistence, state recovery. Session.py exists but socket server doesn't. |
| **File editing** | Read/Edit/Write tools, surgical edits | Executor can do `write` and `edit` actions but no interactive file editing in the TUI beyond PlanEditor. Need general-purpose file editing. |
| **Web access** | WebFetch, WebSearch for research | No web capabilities. Daemons are local-only. |
| **Multi-project scope** | Works on any directory | Scope is implicit in file path. No project switching without restart. |
| **Agent parallelism** | Spawns sub-agents for research, runs them in background | Daemon parallelism exists but no agent-style "go research X and come back." |

### Important — Quality-of-life that makes it daily-driveable

| Gap | Detail |
|-----|--------|
| **Reference memory** | User asks for IPs, URLs, deploy targets constantly. Need a key-value store (`:ref droplet 138.197.23.221`, `:ref` to list). |
| **Command history persistence** | CommandScreen has session history but it's lost on restart. |
| **Health dashboard** | `:status` should show systemd timers, disk, running daemons, last sync times. |
| **Deployment tracking** | Know what version is on what box. `:deploy` command. |
| **Book/document ingestion** | User wants all their books accessible as context. Need a document store with chunked retrieval. |
| **Diary/journal mode** | Stream-of-consciousness writing with embedded AI critique. Not a plan, not a chat — a document you write in where daemons annotate. |
| **Cost tracking** | User is cost-conscious. Show token usage per daemon, per session, cumulative. |

### Nice to Have — Differentiation from Claude Code

| Gap | Detail |
|-----|--------|
| **Daemon personality persistence** | ADR-012. Daemons that learn your preferences over time. |
| **Inter-daemon communication** | ADR-010. Daemons coordinate without blocking the user. |
| **Plugin ecosystem** | ADR-009. Gastown agent types as plugins. |
| **Branch-per-daemon** | From gastown analysis. Each daemon works on its own git branch. |
| **Heartbeat/stall detection** | Daemons that notice when other daemons are stuck. |

## Usage Pattern Insights for Design

### 1. Context burns fast → need focused context
Rob exhausts context 2.3 times per session on average. Reeree's focused-context-per-step design (ADR-006) is the right answer. Each daemon gets only what it needs, not the full conversation history.

### 2. Corrections cluster around voice/style → daemon profiles
25% of correction messages are about tone (too verbose, too cute, too anthropomorphized, wrong register). This is exactly what daemon personality profiles (ADR-012) solve — learn the voice once, apply it every time.

### 3. Topic switching is normal → path-based scope
Rob jumps between topics mid-session constantly. Scope derived from the document path is the right model — open a different file and all context updates automatically.

### 4. Stream-of-consciousness input → reeree's plan format
Rob's natural input is terse, typo-heavy, rapid-fire multi-message bursts that form a single thought. The plan file captures this — he writes fragments, daemons interpret them. No need for polished prompts.

### 5. He wants to see the plan before execution → plan-is-the-interface
88 references to planning across sessions. He always wants to see what will happen before it happens. The editable plan file is exactly right.

### 6. Profanity and directness are normal → ship's computer voice
The correction patterns confirm: don't sanitize his input, don't add politeness, don't hedge in output. Ship's computer is the right default.

### 7. Late-night marathon sessions → persistence is critical
Most work happens 11pm-7am. Sessions routinely run 3-6 hours. Terminal death mid-session would be catastrophic. Daemon persistence (ADR-001) is the answer.

## Next Steps

1. **Session persistence** — finish socket server so daemons survive terminal death
2. **Reference memory** — simple key-value store for IPs, URLs, deploy targets
3. **Document ingestion** — chunked retrieval for books, diary entries, repo docs
4. **Diary/writing mode** — document editing with daemon annotations
5. **Daemon profiles** — ADR-012, start with manual YAML profiles
6. **Web access** — at minimum, web search for research daemons
7. **Remote execution** — SSH-through-reeree for sysadmin mode

---

> **Core Planning Documents:** [Values](../VALUES.md) → [Implementation](../IMPLEMENTATION.md) → [Plan](../PROJECT_PLAN.md) → [Cost](../COST.md) → [Revenue](../REVENUE.md) → [Profit](../PROFIT.md)
