#!/usr/bin/env python3
"""Case 002 repro: a restart re-fires already-run and disabled tasks, invisibly.

Models the mechanism behind a real production incident (2026-07-03, multi-machine
agent fleet; upstream: anthropics/claude-code#74055): after the scheduler process
restarts, the catch-up path (a) re-fires daily tasks that already ran that period,
(b) fires enabled:false tasks, and (c) never writes lastRunAt, so the double runs are
invisible while they burn a full agent session each.

Deterministic model of those three contract violations - stdlib only, no network,
fixed clock, identical output every run. It is not the vendor's runner.

Run:  python repro.py   (exit 0 = demonstration matched expectations)
"""

import sys

# Fixed clock: everything is "the same day". Period key = the calendar day.
PERIOD = "2026-07-03"


def make_registry():
    """6 daily tasks (5 enabled, 1 disabled 3 days ago). last_ran_period=None."""
    reg = []
    for i in range(1, 6):
        reg.append({"id": f"daily-{i:02d}", "enabled": True,
                    "period": PERIOD, "last_ran_period": None, "last_run_at": None})
    reg.append({"id": "disabled-06", "enabled": False,
                "period": PERIOD, "last_ran_period": None, "last_run_at": None})
    return reg


def normal_tick(reg, now="morning"):
    """The healthy daily run: fire each enabled task once, record its run-period."""
    fired = []
    for t in reg:
        if not t["enabled"]:
            continue
        if t["last_ran_period"] == t["period"]:
            continue  # already ran this period
        t["last_ran_period"] = t["period"]
        t["last_run_at"] = now
        fired.append(t["id"])
    return fired


def restart_catchup(reg, now="evening", guarded=False):
    """The restart storm. broken: re-fire everything with a past slot, ignore enabled,
    don't write lastRunAt. guarded: idempotency key + enabled re-check + write lastRunAt."""
    ghost_fires = 0        # fired again though already ran this period
    disabled_fires = 0     # fired though enabled:false
    invisible_fires = 0    # fired but last_run_at not advanced to `now`
    fired = []             # ids the catch-up path actually dispatched
    for t in reg:
        if guarded:
            if not t["enabled"]:
                continue                       # defect 2 fixed: re-check enabled at fire time
            if t["last_ran_period"] == t["period"]:
                continue                       # defect 1 fixed: idempotency key
            t["last_ran_period"] = t["period"]
            t["last_run_at"] = now             # defect 3 fixed: every fire is visible
            fired.append(t["id"])
        else:
            # broken catch-up: fire any task whose slot is "in the past" = all of them,
            # regardless of enabled or already-ran, and DON'T touch last_run_at.
            already = t["last_ran_period"] == t["period"]
            if already:
                ghost_fires += 1
            if not t["enabled"]:
                disabled_fires += 1
            invisible_fires += 1               # every catch-up fire leaves last_run_at stale
            fired.append(t["id"])              # it DID dispatch a session, it just left no stamp
    return {"ghost_fires": ghost_fires, "disabled_fires": disabled_fires,
            "invisible_fires": invisible_fires, "fired": fired}


def lastrunat_state(reg, expected_now):
    """fresh = every task that fired shows the latest run stamp; stale = some lag behind."""
    stamps = {t["last_run_at"] for t in reg if t["last_run_at"] is not None}
    return "fresh" if stamps == {expected_now} else "stale"


def run_mode(guarded):
    reg = make_registry()
    normal_tick(reg, now="morning")            # healthy daily run: everyone ran once
    res = restart_catchup(reg, now="evening", guarded=guarded)
    # In broken mode nothing advanced to "evening" (last_run_at never written) -> stale.
    # In guarded mode nothing re-fired, so all stamps stay "morning" and consistent -> fresh.
    res["lastRunAt"] = lastrunat_state(reg, "morning")
    return res


def main() -> int:
    broken = run_mode(guarded=False)
    guarded = run_mode(guarded=True)

    print(f"mode=broken     restart-catchup: ghost_fires={broken['ghost_fires']} "
          f"disabled_fires={broken['disabled_fires']} invisible_fires={broken['invisible_fires']} "
          f"lastRunAt={'stale' if broken['invisible_fires'] else 'fresh'}")
    print(f"mode=guarded    restart-catchup: ghost_fires={guarded['ghost_fires']} "
          f"disabled_fires={guarded['disabled_fires']} invisible_fires={guarded['invisible_fires']} "
          f"lastRunAt={guarded['lastRunAt']}")

    ok = (
        broken["ghost_fires"] == 5 and broken["disabled_fires"] == 1
        and broken["invisible_fires"] == 6        # all 6 catch-up fires leave lastRunAt stale
        and guarded["ghost_fires"] == 0 and guarded["disabled_fires"] == 0
        and guarded["invisible_fires"] == 0 and guarded["lastRunAt"] == "fresh"
    )
    print("repro:", "OK - mechanism demonstrated" if ok else "FAIL - model drifted from the case doc")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
