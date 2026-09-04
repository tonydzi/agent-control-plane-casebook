#!/usr/bin/env python3
"""Case 007 tests: the confident zero reproduces, the strict reader and the guard kill it.

Plain asserts, stdlib only:  python test_lookup_guard.py
`--against-broken-reader` reruns the guard tests wired to the defaulting reader; they
MUST fail (exit 1). That runnable red state is the proof the guard tests can actually
catch the bug - a test that never fails proves nothing.
Each test prints what it counted.
"""

import sys

from repro import (LIVE_SIZE, TARGET, AmbiguousRegistry, guard, lookup_defaulting,
                   lookup_strict, make_registry)

STRICT = True  # flipped to False by --against-broken-reader


def _lookup(reg, target):
    if STRICT:
        return lookup_strict(reg, target)
    return lookup_defaulting(reg, target)


def test_vestigial_key_lies() -> str:
    """The bug: the expected key exists but holds one leftover record. Zero, no error."""
    reg = make_registry(with_vestigial_key=True)
    r = lookup_defaulting(reg, TARGET)
    assert r["hits"] == 0, f"hits={r['hits']}"
    assert r["population"] == 1, f"population={r['population']}"
    assert r["error"] is None, f"error={r['error']}"
    return f"hits={r['hits']} population={r['population']} error=none"


def test_absent_key_falls_through_to_the_object() -> str:
    """The bug, second face: key gone, the default hands back the registry object.

    Iteration then yields top-level keys, so the population is a count of KEYS - a
    number with no relationship to records - and the answer is still a silent zero.
    """
    reg = make_registry(with_vestigial_key=False)
    r = lookup_defaulting(reg, TARGET)
    assert r["hits"] == 0, f"hits={r['hits']}"
    assert r["population"] == 3, f"population={r['population']}"
    assert r["error"] is None, f"error={r['error']}"
    return f"hits={r['hits']} population={r['population']} (top-level keys) error=none"


def test_the_entry_is_actually_registered() -> str:
    """The reader must find an entry that IS in the live collection."""
    reg = make_registry(with_vestigial_key=True, declare=True)
    r = _lookup(reg, TARGET)
    assert r["hits"] == 1, f"hits={r['hits']}"
    assert r["population"] == LIVE_SIZE, f"population={r['population']}"
    return f"hits={r['hits']} of {r['population']} searched={r['searched']}"


def test_undeclared_ambiguity_is_refused() -> str:
    """Two top-level lists and no declaration: refuse to guess, do not answer zero."""
    reg = make_registry(with_vestigial_key=True)
    try:
        r = _lookup(reg, TARGET)
    except AmbiguousRegistry as exc:
        return f"refused: {exc}"
    raise AssertionError(
        f"answered instead of refusing: hits={r['hits']} searched={r['searched']}")


def test_guard_clears_only_a_credible_zero() -> str:
    """The guard alarms on both broken reads and stays quiet on the strict one."""
    drifted = make_registry(with_vestigial_key=True)
    cleaned = make_registry(with_vestigial_key=False)
    fixed = make_registry(with_vestigial_key=True, declare=True)
    assert guard(lookup_defaulting(drifted, TARGET), drifted).startswith("ALARM")
    assert guard(lookup_defaulting(cleaned, TARGET), cleaned).startswith("ALARM")
    verdict = guard(_lookup(fixed, TARGET), fixed)
    assert verdict == "ok", f"guard on the good read said: {verdict}"
    return "2 broken reads alarmed, the good read cleared"


TESTS = [test_vestigial_key_lies, test_absent_key_falls_through_to_the_object,
         test_the_entry_is_actually_registered, test_undeclared_ambiguity_is_refused,
         test_guard_clears_only_a_credible_zero]


def main() -> int:
    global STRICT
    if "--against-broken-reader" in sys.argv:
        STRICT = False
        print("MODE: guard tests wired to the defaulting reader (expected: RED)")
    failures = 0
    for test in TESTS:
        try:
            print(f"PASS {test.__name__}: {test()}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
    print(f"{len(TESTS) - failures}/{len(TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
