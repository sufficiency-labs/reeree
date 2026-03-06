# Keyboard Shortcuts

Reeree uses vim-style modal editing. Three modes: VIEW (rich display), EDIT (YAML editing), COMMAND (`:` commands). VIEW is the default — it shows the plan in a rich, read-only display. EDIT mode drops into raw YAML with vim-style NORMAL/INSERT sub-modes.

## Modes

| Mode | Status bar | How to enter | How to exit |
|------|-----------|-------------|------------|
| VIEW | `[VIEW]` green | Default; `Escape` from EDIT NORMAL | — |
| EDIT NORMAL | `[EDIT]` blue | `:edit` from VIEW | `Escape` → VIEW |
| EDIT INSERT | `[INSERT]` yellow | `i`, `a`, or `o` from EDIT NORMAL | `Escape` → EDIT NORMAL |
| COMMAND | `[COMMAND]` cyan | `:` from VIEW or EDIT NORMAL | `Enter` (execute) or `Escape` (cancel) |
| FILE VIEWER | Shows file path | `:file path` | `:q` |

## VIEW Mode

The default mode. Plan is displayed as a rich, read-only view. No text editing — navigation and commands only.

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
| `:` | Enter COMMAND mode |
| `Tab` | Cycle focus: Plan → Exec Log → Chat (if open) → Plan |
| `Ctrl+W` | Same as Tab |

Note: `i` is **not** bound in VIEW mode. Use `:edit` to enter EDIT mode.

## EDIT Mode

Entered via `:edit`. The plan is shown as raw YAML. EDIT mode has two sub-modes that mirror vim behavior.

### EDIT NORMAL (read-only YAML navigation)
| Key | Action |
|-----|--------|
| `j` | Cursor down |
| `k` | Cursor up |
| `h` | Cursor left |
| `l` | Cursor right |
| `g` | Start of line |
| `G` | End of line |
| `i` | Enter INSERT sub-mode |
| `a` | Enter INSERT sub-mode (synonym for `i`) |
| `o` | New line + INSERT sub-mode |
| `Escape` | Return to VIEW mode |

### EDIT INSERT (typing into YAML)

Full text editing. Arrow keys, backspace, typing all work normally. `h`/`j`/`k`/`l` are **not** intercepted — they type literal characters.

| Key | Action |
|-----|--------|
| `Escape` | Return to EDIT NORMAL (parses YAML back into plan) |

## COMMAND Mode

Opened by pressing `:` in VIEW or EDIT NORMAL mode. Command line appears at bottom.

| Key | Action |
|-----|--------|
| `Enter` | Execute command |
| `Escape` | Cancel without executing |
| `Up` | Previous command in history |
| `Down` | Next command in history |

Command history holds up to 100 entries per session.

## File Viewer

Opened via `:file path`. Mirrors EDIT NORMAL/INSERT bindings for navigation and editing. These commands are intercepted:

| Command | Action |
|---------|--------|
| `:q` | Close viewer, return to plan |
| `:q!` | Force close viewer |
| `:w` | Save file to disk; also processes any `[machine: ...]` annotations as machine tasks |
| `:wq` | Save, process machine tasks, and close |

`[machine: ...]` annotations are inline markers in files that describe tasks for the daemon to execute. When the file is saved with `:w`, these annotations are extracted and dispatched automatically.

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

## Saving & Dispatching

| Command | Action |
|---------|--------|
| `:w` | Save — exits edit mode if editing; saves file if in file viewer (also processes machine tasks) |
| `:go` | Dispatch next pending step |
| `:go N` | Dispatch step N |
| `:go all` | Dispatch ALL pending steps |
| `:W` | Dispatch ALL pending steps (alias for `:go all`) |

## Plan Editing

| Command | Action |
|---------|--------|
| `:edit` | Enter EDIT mode (raw YAML editing) |

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
