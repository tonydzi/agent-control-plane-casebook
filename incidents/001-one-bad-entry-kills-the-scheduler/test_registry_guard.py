#!/usr/bin/env python3
"""Case 001 tests: the bug reproduces, the guard rescues, the alarm fires.

Plain asserts, stdlib only, no test framework needed:  python test_registry_guard.py
Each test prints WHAT it counted, not just a verdict — a counter you can't inspect
is a counter you can't trust.

Red-first, runnable: `python test_registry_guard.py --against-broken-loader` wires the
guard tests to the all-or-nothing behavior and visibly FAILS (exit 1). That red run is
the proof the guard tests can actually catch the bug; its output is pasted in the case
README.
"""

import sys
import tempfile
from pathlib import Path

from repro import (
    NOW_MS,
    RegistryRejected,
    load_all_or_nothing,
    load_quarantine,
    parity_alarm,
    tick,
    write_registry,
)


def make_root(tmp: str, with_bad_entry: bool) -> Path:
    root = Path(tmp) / ("broken" if with_bad_entry else "healthy")
    write_registry(root, with_bad_entry=with_bad_entry)
    return root


def test_bug_reproduces(tmp: str) -> str:
    """All-or-nothing loader: 1 bad entry out of 6 -> the WHOLE registry is rejected."""
    root = make_root(tmp, with_bad_entry=True)
    on_disk = len(list((root / "tasks").glob("*.json")))
    try:
        load_all_or_nothing(root)
        raise AssertionError("expected RegistryRejected, loader accepted a bad registry")
    except RegistryRejected:
        loaded = 0  # the real system degrades to an empty registry and keeps running
    assert on_disk == 6 and loaded == 0, f"on_disk={on_disk} loaded={loaded}"
    return f"on_disk={on_disk} loaded={loaded} (total silent loss)"


def test_quarantine_rescues(tmp: str) -> str:
    """Per-entry quarantine: the 5 valid tasks load and fire; only the bad one is held."""
    root = make_root(tmp, with_bad_entry=True)
    loaded, quarantined = load_quarantine(root)
    fired = tick(loaded, NOW_MS)
    assert len(loaded) == 5, f"loaded={len(loaded)}"
    assert len(fired) == 5, f"fired={len(fired)}"
    assert quarantined == ["task-06"], f"quarantined={quarantined}"
    return f"loaded={len(loaded)} fired={len(fired)} quarantined={quarantined}"


def test_parity_alarm(tmp: str) -> str:
    """The guard alarms on ANY disk/memory gap — including quarantine's own 6!=5."""
    root = make_root(tmp, with_bad_entry=True)
    on_disk = len(list((root / "tasks").glob("*.json")))
    loaded, _ = load_quarantine(root)
    # Premise: the alarm's job is to tell PARTIAL loss from TOTAL loss, so a partial
    # load must actually exist. Without this line the test passed against the broken
    # loader too (loaded=0 makes both cases look identical) — a guard test that agrees
    # with the failure it hunts. Found by measuring how many checks flip: 1 of 4.
    assert len(loaded) == on_disk - 1, (
        f"quarantine must rescue {on_disk - 1} of {on_disk}, got {len(loaded)}"
    )
    assert parity_alarm(on_disk, 0), "silent total loss must alarm"
    assert parity_alarm(on_disk, len(loaded)), "quarantined entry must still alarm"
    assert not parity_alarm(6, 6), "full parity must stay quiet"
    return f"alarm(6,0)=True alarm(6,{len(loaded)})=True alarm(6,6)=False"


def test_healthy_registry(tmp: str) -> str:
    """No bad entry: both loaders agree, everything fires, the guard stays quiet."""
    root = make_root(tmp, with_bad_entry=False)
    strict = load_all_or_nothing(root)
    loaded, quarantined = load_quarantine(root)
    fired = tick(loaded, NOW_MS)
    assert len(strict) == len(loaded) == len(fired) == 6, (
        f"strict={len(strict)} loaded={len(loaded)} fired={len(fired)}"
    )
    assert not quarantined and not parity_alarm(6, len(loaded))
    return f"strict={len(strict)} loaded={len(loaded)} fired={len(fired)} alarm=False"


TESTS = [test_bug_reproduces, test_quarantine_rescues, test_parity_alarm, test_healthy_registry]


def broken_quarantine(root: Path) -> tuple:
    """What the real system effectively does: first bad entry drops EVERYTHING."""
    try:
        return load_all_or_nothing(root), []
    except RegistryRejected:
        return [], []


def strict_argv(known):
    """Refuse unknown arguments (exit 2) instead of silently ignoring them.

    Without this, `test.py --against-broken-typo` runs the GREEN suite and exits 0,
    so "I proved the red mode" describes a command that never ran. That is this
    repo's own subject in miniature: an unparsed flag is an instruction dropped
    without a trace, and the exit code still says success.
    """
    for arg in sys.argv[1:]:
        if arg not in known:
            print("unknown argument %r - nothing was run (exit 2). known: %s"
                  % (arg, sorted(known)), file=sys.stderr)
            raise SystemExit(2)


def main() -> int:
    strict_argv({"--against-broken-loader"})
    if "--against-broken-loader" in sys.argv:
        # Red-first mode: run the SAME guard tests against the broken behavior.
        # Expected result: FAIL (exit 1). A guard that stays green here is fake.
        globals()["load_quarantine"] = broken_quarantine
        print("MODE: guard tests wired to the broken all-or-nothing loader (expected: RED)")
    failures = 0
    for test in TESTS:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                detail = test(tmp)
                print(f"PASS {test.__name__}: {detail}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {test.__name__}: {exc}")
    print(f"{len(TESTS) - failures}/{len(TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
