# Keyboard Shortcuts

Reeree uses vim-style modal editing. Three modes: NORMAL (navigation), INSERT (editing), COMMAND (`:` commands). A fourth mode activates when a file is open in the viewer overlay.

## Modes

| Mode | Status bar | How to enter | How to exit |
|------|-----------|-------------|------------|
| NORMAL | `[NORMAL]` green | Default; `Escape` from INSERT | — |
| INSERT | `[INSERT]` yellow | `i`, `a`, or `o` from NORMAL | `Escape` |
| COMMAND | `[COMMAND]` cyan | `:` from NORMAL | `Enter` (execute) or `Escape` (cancel) |
| FILE VIEWER | Shows file path | `:file path` | `:q` |

## NORMAL Mode

### Navigation
| Key | Action |
|-----|--------|
| `j` | Cursor down |
| `k` | Cursor up |
| `h` | Cursor left |
| `l` | Cursor right |
| `g` | Start of line |
| `G` | End of line |

### Mode switching
| Key | Action |
|-----|--------|
| `i` | Enter INSERT mode |
| `a` | Enter INSERT mode (synonym for `i`) |
| `o` | New line + INSERT mode |
| `:` | Enter COMMAND mode |

### Pane focus
| Key | Action |
|-----|--------|
| `Tab` | Cycle focus: Plan → Exec Log → Chat (if open) → Plan |
| `Ctrl+W` | Same as Tab |

## INSERT Mode

Full text editing. Arrow keys, backspace, typing all work normally. `h`/`j`/`k`/`l` are **not** intercepted — they type literal characters.

| Key | Action |
|-----|--------|
| `Escape` | Return to NORMAL mode (parses YAML back into plan) |

## COMMAND Mode

Opened by pressing `:` in NORMAL mode. Command line appears at bottom.

| Key | Action |
|-----|--------|
| `Enter` | Execute command |
| `Escape` | Cancel without executing |
| `Up` | Previous command in history |
| `Down` | Next command in history |

Command history holds up to 100 entries per session.

## File Viewer

Opened via `:file path`. Mirrors NORMAL/INSERT bindings for navigation and editing. These commands are intercepted:

| Command | Action |
|---------|--------|
| `:q` | Close viewer, return to plan |
| `:q!` | Force close viewer |
| `:w` | Save file to disk |
| `:wq` | Save and close |

Other commands (`:chat`, `:help`, etc.) pass through normally.

## Chat Panel

Opened via `:chat`. Input field at bottom of chat pane.

| Key | Action |
|-----|--------|
| `Enter` | Send message to daemon |
| `Escape` | Close chat, return to plan |

Special text commands: `exit`, `close`, `quit`, `q` close the panel. `done` saves config in setup mode.

---

# Commands Reference

## Plan Execution

| Command | Action |
|---------|--------|
| `:w` | Execute plan up to cursor step |
| `:w N` | Execute step N only |
| `:w 1 3 5` | Execute specific steps |
| `:w "description"` | Create new step and execute it |
| `:w N "annotation"` | Annotate step N, then execute |
| `:W` | Execute ALL pending steps |
| `:W 1 3 5` | Execute specific steps |
| `:go` | Execute next 2 pending steps |

## Step Management

| Command | Action |
|---------|--------|
| `:add "description"` | Create a new step |
| `:del N` | Delete step N (1-indexed) |
| `:move N M` | Move step N to position M |

## File & View

| Command | Action |
|---------|--------|
| `:file path` | Open file in viewer overlay |
| `:diff` | Show diff for step at cursor |
| `:diff N` | Show diff for step N |
| `:log` | Show daemon 1's output |
| `:log N` | Show daemon N's output |

## Daemon Control

| Command | Action |
|---------|--------|
| `:pause N` | Pause daemon N |
| `:resume N` | Resume daemon N |
| `:kill N` | Kill daemon N and its children |

## Configuration

| Command | Action |
|---------|--------|
| `:set model <name>` | Change LLM model |
| `:set autonomy <level>` | Set autonomy: `low`, `medium`, `high`, `full` |
| `:setup` | Launch setup wizard |

Autonomy levels:
- **low** — approve everything
- **medium** — auto-approve reads, ask about writes (default)
- **high** — auto-approve reads + writes, ask about shell
- **full** — auto-approve all

## Scope & Context

| Command | Action |
|---------|--------|
| `:cd path` | Push into subdirectory scope |
| `:cd ..` | Pop to parent scope |
| `:cd` | Show current scope |
| `:scope` | Show scope stack |

## Analysis

| Command | Action |
|---------|--------|
| `:propagate` | Crawl cross-references, check coherence |
| `:cohere doc1 doc2` | Check coherence across specified files |

## Session

| Command | Action |
|---------|--------|
| `:chat` | Toggle chat panel (executor daemon) |
| `:chat executor` | Chat with executor daemon |
| `:chat coherence` | Chat with coherence daemon |
| `:chat state` | Chat with state daemon |
| `:close` | Close chat panel |
| `:undo` | Revert last step (git revert) |
| `:help` | Show quick reference |
| `:q` | Save plan and quit |
| `:q!` | Force quit |
| `:wq` | Save and quit |

> Core Planning Documents: [Values](../VALUES.md) | [Implementation](../IMPLEMENTATION.md) | [Plan](../PROJECT_PLAN.md) | [Cost](../COST.md) | [Revenue](../REVENUE.md) | [Profit](../PROFIT.md)
