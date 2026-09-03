# 001 — One malformed field silently kills the whole scheduler registry

**Family:** silent task loss · registry load path
**Status:** reproduced · upstream open
**Upstream:** [anthropics/claude-code#90533](https://github.com/anthropics/claude-code/issues/90533)
(filed by us) · independent reports in the same family by other users:
[#85565](https://github.com/anthropics/claude-code/issues/85565),
[#86115](https://github.com/anthropics/claude-code/issues/86115)

## Symptom

Every scheduled agent routine on the node stops firing at once — in our production
incident, **35 tasks went dark for 55 hours**. Nothing on screen changes. Every
liveness proxy stays green: processes run, the dispatcher heartbeat is alive, and the
scheduler even keeps *writing* bookkeeping fields into the very registry file it can
no longer load. The failure was caught by an external output-freshness watchdog, not
by the platform.

## Root cause

Two cooperating causes, both required (as observed on desktop app 1.37937.3.0 /
CLI 2.1.246 — see Evidence; the vendor may have changed either side since):

1. **Writer/loader contract drift.** The platform's own `update_scheduled_task` tool
   documents and writes `fireAt` as an ISO 8601 string. The registry loader validates
   `fireAt` as epoch milliseconds. The platform's write path produces data its own
   read path rejects.
2. **All-or-nothing registry validation.** On the first invalid entry, the loader
   rejects the *entire* registry (in the real system, a `ZodError` on
   `loadScheduledTasksFromDisk`) instead of quarantining the one bad entry. One
   malformed field out of 35 tasks → zero tasks loaded → every routine silently dead.

## Deterministic repro

[`repro.py`](repro.py) models the mechanism with a fixed clock and stdlib only: it
writes a registry of 6 task files — 5 valid (`fireAt` epoch ms, due) and 1 with the
exact real-world payload (`"fireAt": "2026-08-27T07:30:00+01:00"` as a string) — then
loads it two ways and ticks the scheduler once.

```
python repro.py
```

Requires Python 3.8+, stdlib only; on systems where `python` isn't aliased, use
`python3`. Expected output, identical every run (exit 0):

```
mode=all-or-nothing  on_disk=6 loaded=0 fired=0 dropped=6 alarm=none (SILENT)
mode=quarantine      on_disk=6 loaded=5 fired=5 quarantined=1 alarm=PARITY on_disk=6 loaded=5
mode=healthy         on_disk=6 loaded=6 fired=6 quarantined=0 alarm=none
repro: OK - mechanism demonstrated
```

What the model does NOT cover: this is not the vendor's code. It reproduces the load
contract and its failure shape, not the app's scheduling internals. The real-world
evidence below is what ties the mechanism to the incident.

## Detection guard

**Registry parity:** count task files on disk, count tasks the scheduler actually
loaded, alarm on mismatch. It is cheap, deterministic, and catches both this case and
the wider family (registry wipes, split-brain registries). The broken mode above is
exactly the state a parity guard turns from silence into a page.

[`test_registry_guard.py`](test_registry_guard.py) proves four things and prints what
it counted: the bug reproduces (0 of 6 loaded), quarantine rescues the rest (5 of 6),
the parity alarm fires on every drop (including quarantine's own 6≠5), and a healthy
registry stays quiet.

```
python test_registry_guard.py
```

A test that never failed proves nothing, so the red state is runnable, not claimed:
`--against-broken-loader` wires the same guard tests to the all-or-nothing behavior
and must FAIL (exit 1). Captured run:

```
$ python test_registry_guard.py --against-broken-loader
MODE: guard tests wired to the broken all-or-nothing loader (expected: RED)
PASS test_bug_reproduces: on_disk=6 loaded=0 (total silent loss)
FAIL test_quarantine_rescues: loaded=0
PASS test_parity_alarm: alarm(6,0)=True alarm(6,0)=True alarm(6,6)=False
PASS test_healthy_registry: strict=6 loaded=6 fired=6 alarm=False
3/4 passed
```

## Fix / mitigation

- **Normalize at the boundary:** accept both shapes on load (number | ISO string →
  epoch ms), or make the write path store what the read path expects. Either closes it.
- **Degrade per entry:** one malformed entry should quarantine that entry, not reject
  the registry.
- **Recovery, verified in production:** converting the one string value to epoch ms
  and fully restarting the app made the dispatcher immediately fire the overdue
  routines; the registry has been healthy since.

**Residual risk:** a running app holds the registry in memory — hand-editing the JSON
is inert until restart, and nothing on screen says so. And a "no routine has fired for
N hours while the dispatcher believes itself healthy" condition still has no surfaced
signal in the platform; the parity guard above is an external compensation, not a fix.

## Evidence

- Production incident, 2026-08 (our multi-machine fleet, Windows node): 35 scheduled
  tasks silent for 55 hours; a `ZodError` (`Invalid input: expected number, received
  string`) at `scheduledTasks[33].fireAt` on every app start; full details, log
  excerpt and both suggested fixes in
  [claude-code#90533](https://github.com/anthropics/claude-code/issues/90533).
- Environment at the time: Windows 11 Pro, Claude desktop app 1.37937.3.0 (MSIX),
  Claude Code CLI 2.1.246.
- Same silent-task-loss family, independently reported by other users: registry wiped
  to `[]` by an app update ([#85565](https://github.com/anthropics/claude-code/issues/85565)),
  paused tasks vanishing from the list ([#86115](https://github.com/anthropics/claude-code/issues/86115)).
