# bd-timew → bd-track 0.5.0 cutover — session adaptation guide

**Audience:** any Claude session (or human operator) currently using `bd-timew`
for time tracking or queue work while the 0.5.0 cutover is in progress.
**Read this fully before running any `bd-timew`/`bd-track` command.**

---

## TL;DR — what to do *right now*

1. **Stop tracking immediately.** Run your `/stop` slash command (or
   `bd-timew stop <your-bead>`). This closes your open Timewarrior interval using
   the *current* (old) tool — which is the **only** thing that can close it
   cleanly. See "Why this matters" below.
2. **Confirm nothing is tracking:** the operator will verify `timew` shows no
   active interval across all sessions.
3. **Go idle.** Do **not** call `start` / `stop` / `switch` / `status` / `queue`
   (or their slash commands) until the operator says the cutover is complete.
   Your session process can stay alive — just don't invoke the tool.
4. **Resume only on the operator's signal**, then read "After the cutover" below
   so you understand what changed.

> If you cannot stop cleanly (e.g. your interval is already orphaned, or you're
> unsure), **tell the operator** — do not try to repair timew state yourself.

---

## Why this matters (the one hard constraint)

The cutover replaces the **Timewarrior** backend with an append-only **JSONL
event log**, and reinstalls the tool via pipx.

- Timewarrior's datastore is **global** — one store shared by every session.
- After the reinstall, `bd-timew` (and `bd-track`) write to the **JSONL** backend
  and have **no knowledge of Timewarrior at all**.
- An interval left **open** at the moment of reinstall is therefore stranded:
  the new tool can't close it, and the historical import **skips open
  intervals**, so the time is lost from the record and dangles in timew forever.

That is the entire reason for the "stop now, then go idle" sequence. Closed
intervals are safe — they get archived by the migration. Open ones are not.

---

## After the cutover — what changed

Once the operator signals completion, here's how your workflow adapts:

### The tool is now `bd-track`

The package, module, and command renamed from `bd-timew` to `bd-track`. The
**`bd-timew` command still works** as a deprecated alias — it prints this to
stderr on every call, then runs normally:

```
warning: `bd-timew` is deprecated and will be removed in a future release;
use `bd-track` instead. Run `bd-track migrate rename` to migrate config/env naming.
```

**That warning is expected — it is not an error.** Your slash commands keep
working through the alias. (The chezmoi pass that rewires the slash commands to
call `bd-track` directly lands separately; until then you may also see stale
"Timewarrior" wording in command output — ignore it.)

The **Beads issue prefix `bd-timew-` is unchanged.** Only the tool renamed.

### No-argument `stop` is now safe

Under the old timew backend, a no-argument `stop` could close *another session's*
interval — the bug this whole rewrite exists to kill. **That bug is gone.** Each
session writes its own log; a no-arg `stop` can only close intervals in *your
own* session. The old "always pass a bead-id to stop" danger note no longer
applies (though passing one is still fine).

### New visibility commands

- **`bd-track active`** — lists every open interval across **all** sessions (your
  own marked `*`). This is the cross-session view the old backend couldn't give.
- **`bd-track report --by <dim> --policy <billing|machine|wallclock>`** —
  aggregates closed time. `--by bead|session|actor|role|group_id|<tag-key>`,
  optional `--since/--until`.

### Session identity is automatic

The backend resolves your session id from `$CLAUDE_CODE_SESSION_ID` with no
cooperation needed, so each Claude session gets its own log file. You normally
never touch this; `bd-track session current` prints the resolved id if you're
curious.

### `status` is now session-scoped

`bd-track status` shows **your** session's interval(s) plus a count of other
active sessions — not a single global interval. Use `active` for the full view.

---

## Quick reference after cutover

| Old habit | New reality |
|---|---|
| `bd-timew <cmd>` | Works (alias, warns); prefer `bd-track <cmd>` |
| no-arg `stop` is dangerous | no-arg `stop` is safe (own session only) |
| one global active interval | per-session logs; use `active` for all |
| (no aggregate view) | `bd-track report …` |
| billing tuple via `.beads/bd-timew.yaml` | `.beads/bd-track.yaml` (old still read) |

Questions or anything unexpected: surface it to the operator rather than
improvising on time-tracking state.
