# 00X — <one-line title: what silently broke>

**Family:** <silent task loss · registry · dispatch · watchdog · encoding · ...>
**Status:** <reproduced | mechanism modeled | awaiting external reproduction>
**Upstream:** <links to public issues, or "none (stack-internal)">

## Symptom

What the operator saw. For control-plane failures this is usually "nothing":
name the green signals that kept lying.

## Root cause

The mechanism in plain words. One paragraph. If there are two cooperating causes
(a writer and a loader disagreeing, a race), name both.

## Deterministic repro

What `repro.py` models, how to run it, and the exact counter output expected.
State explicitly what the model does NOT cover (it is not the vendor's code).

```
python repro.py
python test_<case>.py
```

## Detection guard

The check that turns this silent failure into an alarm. The test file must show
the guard red on the broken behavior and green on the fixed one.

## Fix / mitigation

What actually resolved the incident, verified how. Then residual risk: what can
still bite after the fix.

## Evidence

- Dates, versions, environment.
- Log excerpts (scrubbed to mechanism).
- Upstream / related reports.
