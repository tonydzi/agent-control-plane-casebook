#!/usr/bin/env python3
"""Case 002 tests: the storm reproduces, the guard suppresses all three defects.

Plain asserts, stdlib only:  python test_catchup_guard.py
`--against-broken-runner` reruns the guard tests wired to the broken catch-up path;
they MUST fail (exit 1). That runnable red state is the proof the guard tests can
actually catch the bug - a test that never fails proves nothing.
Each test prints what it counted.
"""

import sys

from repro import make_registry, normal_tick, restart_catchup, lastrunat_state

GUARDED = True  # flipped to False by --against-broken-runner


def _after_restart(guarded):
    reg = make_registry()
    normal_tick(reg, now="morning")
    res = restart_catchup(reg, now="evening", guarded=guarded)
    res["lastRunAt"] = lastrunat_state(reg, "morning")
    return res


def test_storm_reproduces() -> str:
    """Broken catch-up: already-run tasks re-fire, the disabled task fires, all invisible."""
    r = _after_restart(guarded=False)
    assert r["ghost_fires"] == 5, f"ghost_fires={r['ghost_fires']}"
    assert r["disabled_fires"] == 1, f"disabled_fires={r['disabled_fires']}"
    assert r["invisible_fires"] == 6, f"invisible_fires={r['invisible_fires']}"
    return f"ghost={r['ghost_fires']} disabled={r['disabled_fires']} invisible={r['invisible_fires']}"


def test_guard_suppresses() -> str:
    """Guarded catch-up: idempotency + enabled re-check + lastRunAt -> zero ghosts."""
    r = _after_restart(guarded=GUARDED)
    assert r["ghost_fires"] == 0, f"ghost_fires={r['ghost_fires']}"
    assert r["disabled_fires"] == 0, f"disabled_fires={r['disabled_fires']}"
    assert r["invisible_fires"] == 0, f"invisible_fires={r['invisible_fires']}"
    return f"ghost={r['ghost_fires']} disabled={r['disabled_fires']} invisible={r['invisible_fires']}"


def test_disabled_stays_disabled() -> str:
    """A task enabled:false must never be DISPATCHED on catch-up under the guard.

    Asserted on the dispatch list, not on lastRunAt: in broken mode the disabled task
    fires and leaves no stamp, so a stamp-based assertion would pass on the bug.
    """
    reg = make_registry()
    normal_tick(reg, now="morning")
    res = restart_catchup(reg, now="evening", guarded=GUARDED)
    assert "disabled-06" not in res["fired"], f"disabled task dispatched: {res['fired']}"
    return f"disabled-06 not in fired={res['fired']}"


def test_fires_are_visible() -> str:
    """Every task the catch-up path dispatched must carry the new run stamp."""
    reg = make_registry()
    normal_tick(reg, now="morning")
    res = restart_catchup(reg, now="evening", guarded=GUARDED)
    unstamped = [t["id"] for t in reg
                 if t["id"] in res["fired"] and t["last_run_at"] != "evening"]
    assert not unstamped, f"dispatched but unstamped: {unstamped}"
    return f"dispatched={len(res['fired'])} unstamped=0"


TESTS = [test_storm_reproduces, test_guard_suppresses,
         test_disabled_stays_disabled, test_fires_are_visible]


def main() -> int:
    global GUARDED
    if "--against-broken-runner" in sys.argv:
        GUARDED = False
        print("MODE: guard tests wired to the broken catch-up path (expected: RED)")
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
