# Shared agent contract

Portable rules and skills for **any** coding agent. Start at repo-root `AGENTS.md`, then this tree.

| Path | Role |
|------|------|
| `rules/` | Operating rules (same bodies Cursor auto-loads) |
| `skills/` | On-demand workflows (`session-start`, `open-pr`, …) |

**Cursor:** `.cursor/rules` and `.cursor/skills` are symlinks into this folder so Cursor keeps auto-discovering them. Edit files under `.agent/` only — do not duplicate content under `.cursor/`.
