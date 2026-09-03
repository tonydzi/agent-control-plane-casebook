# Contributing

Two kinds of contribution matter here, in this order.

## 1. Reproduce an existing case (most valuable)

Run a case's `repro.py` and `test_*.py` on your machine, or — better — confirm the
mechanism against the real system named in the case's Evidence section. Then open an
issue on that case titled `reproduction: 00X` with:

- your environment (OS, versions),
- the counter output of the repro/test run, verbatim,
- anything that did NOT match the case doc.

Non-reproductions are just as welcome as confirmations. The staged plan (casebook →
scoring harness) advances only on external reproductions, so this is the contribution
that moves the project.

## 2. Add a case

A case must be a **real incident**, not a hypothetical. Requirements:

- Use [`template/CASE.md`](template/CASE.md) for the doc.
- Cite verifiable evidence: a public bug-tracker issue, a log excerpt, or a script a
  stranger can run. "It happened to us, trust us" is not enough.
- Ship a deterministic repro of the mechanism: Python stdlib only, no network, fixed
  clock, same output every run.
- Ship a test that is **red on the broken behavior** and green with the guard/fix. A
  test that never failed proves nothing.
- Abstract to the mechanism. No credentials, no private hostnames, no personal data.

Keep prose short. The format is the value: symptom → root cause → repro → guard →
fix → residual risk → evidence.
