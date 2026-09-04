# 002 — A restart re-fires already-run and disabled tasks, invisibly

**Family:** ghost dispatch · restart catch-up · invisible spend
**Status:** reproduced · upstream open
**Upstream:** [anthropics/claude-code#74055](https://github.com/anthropics/claude-code/issues/74055) (filed by us)

## Symptom

After the scheduler process restarts, it performs a "catch-up storm": daily tasks
that **already ran** that day fire a second time, and tasks that are explicitly
`enabled: false` fire too. In our production incident six daily tasks each fired a
second time within minutes, far from their cron slots, and a task disabled three days
earlier fired at the wrong hour. The duplicate runs are full agent sessions with a
cold context load — one nightly task alone burned ~24.8M tokens across its two runs —
and because these ghost fires **never update `lastRunAt`**, the registry claims the
task never ran. The operator sees a normal registry while the subscription bucket
drains.

## Root cause

Three cooperating defects, each independently a silent-failure amplifier:

1. **Restart catch-up ignores idempotency.** On startup the runner re-fires tasks
   whose cron slot is in the past for the current period, without checking whether the
   task already ran in that period. A restart in the evening re-runs the morning's
   daily tasks.
2. **`enabled: false` is not authoritative at fire time.** The disabled flag is
   honored for the *schedule* but not re-checked when the catch-up path spawns a run,
   so a task disabled days ago still fires.
3. **Ghost fires don't record `lastRunAt`.** A real dispatch updates `lastRunAt`; the
   catch-up path does not. So the one field an operator would use to notice the double
   run stays stale — the spend is invisible in the very tool meant to show it.

## Deterministic repro

[`repro.py`](repro.py) models a scheduler with a fixed clock and a restart event,
stdlib only. It ticks a registry of daily tasks normally (each fires once, records its
run-period), then injects a restart later the same day and runs the catch-up path two
ways.

```
python repro.py
```

Expected output, identical every run (exit 0):

```
mode=broken     restart-catchup: ghost_fires=5 disabled_fires=1 invisible_fires=6 lastRunAt=stale
mode=guarded    restart-catchup: ghost_fires=0 disabled_fires=0 invisible_fires=0 lastRunAt=fresh
repro: OK - mechanism demonstrated
```

(5 enabled daily tasks that already ran this period re-fire = 5 ghosts; the 1
`enabled: false` task fires too; all 6 catch-up fires leave `lastRunAt` stale = 6
invisible.)

What the model does NOT cover: it is not the vendor's runner. It reproduces the three
contract violations (no idempotency key, disabled-not-rechecked, lastRunAt-not-written)
and their observable counts, not the app's scheduling internals. The real-world
evidence below ties the mechanism to the incident.

## Detection guard

Two cheap invariants, both deterministic:

- **Idempotency key per (task, period):** a task that already ran in the current cron
  period is skipped on catch-up. This alone kills defects 1 and 2.
- **Every fire writes `lastRunAt`:** so a ghost fire, if one ever slips through, is at
  least *visible* — an external "no fire recorded but a session was spawned" check can
  then alarm.

[`test_catchup_guard.py`](test_catchup_guard.py) proves the bug reproduces (ghost +
disabled + invisible fires > 0), the guard suppresses all three, `enabled: false` is
honored on catch-up, and every dispatched task carries its run stamp. Run the guard
tests against the broken runner to see them go **red**, on purpose:

```
python test_catchup_guard.py                           # 4/4 pass
python test_catchup_guard.py --against-broken-runner   # 1/4 pass, exit 1
```

Three of the four go red on the broken runner; the fourth is the bug-reproduction
test, green by design in both modes. Note what the last two assert: the **dispatch
list**, not `lastRunAt`. A stamp-based assertion (`the disabled task has no
lastRunAt`) passes on the bug, because the bug is precisely that ghost fires leave no
stamp. A guard test written against the symptom you can see will agree with the
failure you are hunting.

## Fix / mitigation

- **Idempotency:** record a `(taskId, periodKey)` marker on fire; the catch-up path
  skips any task whose current-period marker exists.
- **Re-check `enabled` at fire time,** not only at schedule time.
- **Write `lastRunAt` on every real dispatch,** including catch-up, so ghost runs are
  never invisible.
- **Operator workaround, verified in production:** moving a task's folder out of the
  scheduled-tasks directory prevents its ghost fires (the runner then has no prompt to
  execute); `enabled: false` alone does not.

**Residual risk:** the workaround is destructive to the task (the prompt leaves the
scheduled set), and there is still no surfaced signal for "a session was spawned that
the registry has no record of" — the `lastRunAt`-on-every-fire invariant is what makes
that detectable, but the platform does not yet enforce it.

## Evidence

- Production incident, 2026-07-03 (our fleet, Windows hub): a restart storm ~23:33
  re-fired six daily tasks (crons at 00:20–05:40) minutes apart; a task `enabled:
  false` for three days fired at 20:29; a Monday-only weekly task fired on a Thursday;
  duplicate runs burned tens of millions of tokens with `lastRunAt` never updated.
  Times verified from `~/.claude/projects/**/*.jsonl` session logs. Full write-up:
  [claude-code#74055](https://github.com/anthropics/claude-code/issues/74055).
- Environment: Claude Code 2.1.185 (Windows 11 Pro), desktop app + scheduled-tasks MCP.
- Related in the same silent-task family: the load-contract death of case
  [001](../001-one-bad-entry-kills-the-scheduler/) and the split-store design in
  [claude-code#89840](https://github.com/anthropics/claude-code/issues/89840).
