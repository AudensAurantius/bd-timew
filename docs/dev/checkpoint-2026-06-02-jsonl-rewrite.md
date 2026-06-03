# Session checkpoint — JSONL timetracking rewrite — 2026-06-02

Resume context for the **bd-timew → JSONL event-log timetracking** rewrite
(epic **`bd-timew-nfr`**). Read this, run `bd prime`, then continue working the
**`refactor`** bd-timew queue.

## Why this work exists

Timewarrior has a single global active interval. Parallel Claude sessions
clobbered each other's intervals (time attribution scrambled). The fix: replace
the timew backend with an **append-only JSONL event log** (per-session files,
ULID interval IDs, atomic `O_APPEND`). At the CLI cutover the package is renamed
**`bd-timew` → `bd-track`**.

Full design + reasoning transcript: **`docs/dev/timetracking-architecture.06022026.md`**.
Per-decision detail lives in the closed beads' `design`/`notes` fields.

## Status — done vs next

| Bead | Layer | State |
|------|-------|-------|
| `sfk` | session identity | ✅ closed (`session.py`) |
| `tq9` | log location decision | ✅ closed |
| `blh` | aggregation-policy mechanism | ✅ closed (design only) |
| `ahp` | schema v1 + appender | ✅ closed — **released 0.3.0** (`events.py`) |
| `zzl` | aggregator + reports | ✅ closed — **released 0.4.0** (`aggregate.py`) |
| `9hn` | **CLI cutover + bd-track rename** | ⏭️ **NEXT — head of `refactor` queue** |
| `73v` | migrate timew export → JSONL | queued (after 9hn) |

`bd-timew queue list --scope refactor` → `9hn`, `73v`.
Architecture queue (separate, parked): `7o3` (claude-config integration eval),
`6g4` (post-merge operational layer).

## Key decisions already made (don't relitigate; see bead design fields)

- **Session id** (`sfk`): precedence `--session-id` → `$BD_TIMEW_SESSION_ID` →
  `$CLAUDE_CODE_SESSION_ID` (auto-resolves Claude sessions, no cooperation) →
  per-terminal pointer (`~/.local/state/bd-timew/<project-id>/current-session.json`,
  machine-local, never synced) → generated xkcdpass `word.word.word`. Session ids
  need only be unique among *concurrently active* sessions.
- **Log location** (`tq9`): `<beads_dir>/bd-timew/sessions/<session>.jsonl`
  (rides beads sync; shared `~/.beads` → centralized billing). Fallback
  `~/.local/share/bd-timew/<project-id>/` for server-mode.
- **Schema v1** (`ahp`, `events.py`): one JSON/line; events `start|stop|cancel|correction`;
  **two ULIDs** (`eid` = global order, `interval` = grouping); **flat `tags` list**
  (org-agnostic — billing-tuple *shape* lives in the sidecar config, see `qny`);
  provenance `group_id`/`actor`/`role` on `start`, **mutable only via `correction`**
  (any subset of `{start,stop,tags,group_id,actor,role}`, per-field latest-wins).
  `actor` inferred `claude`/`human` from `$CLAUDE_CODE_SESSION_ID`.
- **Aggregation** (`blh` + `zzl`, `aggregate.py`): flat **partition|collapse** per
  axis → union within a partition, sum across. Axes `group_id/actor/role/`**`session`**
  (session added in zzl so `machine` sums across sessions). Built-in policies
  `machine`/`wallclock`/`billing`. Open/stale intervals **excluded from totals but
  surfaced**. Malformed lines skipped-and-reported.
- **Rename** (`xcw`): → **`bd-track`**, executed at the `9hn` cutover (atomic with
  the backend swap).
- **Versioning** (`2nu`): SemVer, 0.x **minor-per-validated-layer**; CHANGELOG entry
  each bump; 1.0.0 reserved until proven in real billing.

## `9hn` — the next bead (what it entails)

Re-wire the CLI off timew onto the JSONL backend, preserving the command surface,
**and execute the bd-track rename**. Big blast radius — `pyproject` (name +
`[project.scripts]`), the executable, `install.sh`, systemd templates, and every
wrapper/skill (`/start /stop /switch /status`, the `time-tracking` + `work-queue`
skills). Add `active` (open intervals across ALL sessions — the multi-active view
timew can't give). Bumps to **0.5.0**. **Start with a design checkpoint** (the
established rhythm for implementation beads). Recommend `/clear` before starting —
this is a clean seam; the cutover doesn't depend on aggregator internals.

## Deferred / companion beads (filed, not lost)

- `an7` — hierarchical nested-subtotal reporting (notes carry full mechanism).
- `wav` — incremental summary cache w/ watermark (notes carry the late-correction subtlety).
- `qny` — generalize billing config to arbitrary tuple shapes.
- `7bh` — update README/skills/AGENTS docs (comprehensive pass at the cutover; CHANGELOG per bump).

## Working notes

- **Build/test:** `uv run pytest -q` (116 passing), `uv run ruff check`.
  Dev executable: `uv run bd-timew …` (the installed `~/.local/bin/bd-timew` is the
  old version; `.venv` is editable). `mise`/`uv_venv_auto` only fires in interactive
  shells.
- **timew clobbering is expected** during this work — the installed CLI still drives
  timew's single active interval, so tracked intervals here get clobbered. That's the
  very thing being fixed; ignore it until the cutover.
- Code so far: `src/bd_timew/{session,events,aggregate}.py` + matching `tests/test_*.py`.
