# 007 — A registry that grew a second top-level list makes readers report a confident zero

**Family:** registry shape drift · defaulting accessor · false zero
**Status:** reproduced · upstream open
**Upstream:** [anthropics/claude-code#82056](https://github.com/anthropics/claude-code/issues/82056)
(same family at the platform level: a consumer cannot tell a whole index from a
truncated one from none at all)

## Symptom

A control-plane reader answers **0** for something that is registered. Not an error,
not a traceback, not a warning — a number, in the same format as the true answer. In
our incident a routine checking whether an upstream thread was on the watch list
printed `82056 entries: 0`; the thread had been registered by another node of the
fleet the same day. The zero came within a second of being written into the incident
journal as a finding.

This is the load-bearing property of the whole class: **a false zero is not a failure
mode, it is an answer.** A crash gets fixed in a minute. A zero flows into the report,
into the operator's model of the world, and into the next decision.

## Root cause

Two independently harmless things, cooperating:

1. **The registry grew a second top-level collection.** It began as one list. A later
   feature added another key, the live records moved into it, and the older,
   more canonical-sounding key (`items`) kept exactly one leftover record. Nothing in
   the file says which collection is authoritative — the shape is now ambiguous, and
   ambiguity is resolved by whoever reads it, differently each time.
2. **The reader defaults to a non-empty container of the wrong type:**
   `d.get("items", d)`. That accessor has two silent failure faces, and neither raises:
   - the key **exists but is vestigial** → the reader searches the wrong, tiny list;
   - the key **is gone** → the default hands back the registry object itself, and
     iterating a dict yields its **keys**, which are strings and never match a record
     predicate.

The combination converts a *shape* error into a *value* answer. Python will happily
iterate the fallback, count zero matches, and return. The population searched — 1
record, or 3 top-level keys — is never printed next to the zero, so nothing in the
output distinguishes it from a genuine zero out of 129.

## Deterministic repro

[`repro.py`](repro.py) models a watch registry holding 129 live records plus one
vestigial record under the older key, and reads it three ways: the defaulting reader
against the drifted file, the same reader against a file where the old key was tidied
away, and a strict reader that requires the registry to declare its record collection.
Stdlib only, fixed data.

```
python repro.py
```

Expected output, identical every run (exit 0):

```
mode=vestigial-key          lookup(82056): hits=0 population=1    searched=items                        error=none
mode=absent-key-fallback    lookup(82056): hits=0 population=3    searched=<the registry object itself> error=none
mode=strict-declared        lookup(82056): hits=1 population=129  searched=watched                      error=none
mode=strict-undeclared      lookup(82056): refused -> top-level lists ['items', 'watched'], none declared authoritative
guard(vestigial-key)       = ALARM: zero out of 1 searched while the file holds 129 records
guard(absent-key-fallback) = ALARM: searched <the registry object itself>, which is not a record collection
guard(strict-declared)     = ok
repro: OK - mechanism demonstrated
```

Read the three populations as one sentence: the same lookup searched 1 record, then 3
dictionary keys, then 129 records, and only the last number has anything to do with
the question asked. Two of the three answers were zero and neither raised.

What the model does NOT cover: it is not the vendor's code. It reproduces the shape
drift, the defaulting accessor and the resulting counts, not any product's registry
internals. The real-world evidence below ties the mechanism to the incident.

## Detection guard

The useful property of this guard is that it **does not need to know the right
answer** — which matters, because the whole class only bites when nobody knows it.
Two invariants:

- **The collection searched must be an actual record collection of the file.**
  Searching "the registry object itself" is an alarm regardless of the count.
- **A zero is credible only out of the largest record collection in the file.** Zero
  out of 1 record, while 129 sit on disk, is an alarm, not an answer. Generalised:
  *never print a zero without the size of the population you searched next to it.*

Plus the structural fix that makes both unnecessary: the reader names its collection
explicitly and **refuses to guess** when the file has more than one top-level list and
declares none authoritative.

[`test_lookup_guard.py`](test_lookup_guard.py) proves the bug reproduces in both of its
faces, that the strict reader finds the entry that is really registered, that ambiguity
is refused rather than answered, and that the guard alarms on both broken reads while
clearing the good one.

```
python test_lookup_guard.py                          # 5/5 pass
python test_lookup_guard.py --against-broken-reader  # 2/5 pass, exit 1
```

Three of the five go red on the defaulting reader; the two that stay green are the
bug-reproduction tests, green by design in both modes.

## Fix / mitigation and residual risk

- **Declare the record collection in the file** (`"schema": {"records": "watched"}`),
  or keep exactly one top-level list. A registry that cannot say where its records
  live has delegated that decision to every reader separately.
- **Ban the defaulting accessor on registries.** `d["watched"]` raises on drift, which
  is the correct behaviour; `d.get(k, d)` invents an answer. The dangerous form is
  specifically a default that is *iterable* — an empty-list default at least yields an
  honest, provably-empty population.
- **Print the searched population beside every zero.** One line, no new machinery, and
  it is what actually caught this one: dumping `{k: len(d[k]) for k in d}` before
  writing the finding showed both keys.
- **Delete vestigial collections when the records move.** The leftover single record is
  what makes the wrong read look plausible.

**Residual risk:** a strict reader still cannot distinguish a *stale* registry from a
fresh one — it will confidently search the declared collection of a file nobody has
written to in a week. And a vestigial key that holds a genuinely plausible number of
records defeats the population heuristic; only the declaration kills that case.

## Evidence

- Production incident, 2026-08-24 (our fleet, macOS node, unattended routine): a check
  for whether upstream thread `anthropics/claude-code#82056` was on an outbound watch
  registry printed `82056 entries: 0`. The file held two top-level lists — the live one
  with 129 records and an older key with 1 vestigial record — and the reader used
  `d.get("items", d)`. The thread *was* registered, by the Windows hub, the same day.
  Caught not by a check but by printing the size of every top-level list before writing
  the finding.
- Recurrence: a family query over our incident journal returns 6 dated neighbours in
  the three weeks around this one (2026-08-13 to 2026-09-01). Two are the same defect
  under a different name: 2026-09-01, a routine whose sampling window was smaller than
  the accumulated backlog silently dropped the remainder; 2026-08-21, two writers exited
  0 in thirteen seconds having produced nothing. The rest are neighbours, not instances.
  We report the search result rather than a class verdict: the point is that the shape
  recurs across unrelated readers, not that six incidents were identical.
- Upstream, the same family one layer up:
  [claude-code#82056](https://github.com/anthropics/claude-code/issues/82056) — a
  session cannot determine whether its auto-memory index loaded whole, truncated, or
  not at all. Same shape of harm: the consumer sees content, cannot tell how much of
  the population it represents, and has no error to go on.
- Environment: Claude Code on a Windows 11 hub and macOS nodes, scheduled agent
  routines, JSON registries on a synced filesystem.
- Related here: case [001](../001-one-bad-entry-kills-the-scheduler/) is the same harm
  from the writer's side — a loader that answers "0 tasks" instead of raising.
