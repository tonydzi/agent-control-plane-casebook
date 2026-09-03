#!/usr/bin/env python3
"""Case 001 repro: one malformed field silently kills the whole scheduler registry.

Models the mechanism behind a real production incident (2026-08, multi-machine agent
fleet; upstream: anthropics/claude-code#90533): a task writer stored `fireAt` as an
ISO 8601 string, the registry loader required epoch milliseconds and rejected the
ENTIRE registry on the first invalid entry. 35 scheduled tasks went silently dark for
55 hours; every liveness proxy stayed green.

This script is a deterministic model of that load contract — stdlib only, no network,
fixed clock, identical output every run. It is not the vendor's code.

Run:  python repro.py   (exit 0 = demonstration matched expectations)
"""

import json
import sys
import tempfile
from pathlib import Path

# Fixed clock: 2026-09-02T08:00:00Z. The repro never reads the wall clock.
NOW_MS = 1788336000000

# The exact real-world payload shape from the incident: a string where the loader
# expects epoch milliseconds.
BAD_FIREAT = "2026-08-27T07:30:00+01:00"


class RegistryRejected(Exception):
    """The all-or-nothing loader's failure mode: one bad entry, zero tasks."""


def write_registry(root: Path, with_bad_entry: bool) -> int:
    """Write 6 due tasks; task-06 is malformed when with_bad_entry. Returns file count."""
    tasks_dir = root / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, 7):
        fire_at = BAD_FIREAT if (with_bad_entry and i == 6) else NOW_MS - 60_000
        entry = {"id": f"task-{i:02d}", "enabled": True, "fireAt": fire_at}
        (tasks_dir / f"task-{i:02d}.json").write_text(json.dumps(entry), encoding="utf-8")
    return len(list(tasks_dir.glob("*.json")))


def validate(entry: dict) -> dict:
    """The loader's contract: fireAt must be epoch milliseconds (int, not bool)."""
    fire_at = entry.get("fireAt")
    if isinstance(fire_at, bool) or not isinstance(fire_at, int):
        raise ValueError(
            f"invalid_type at {entry.get('id', '?')}.fireAt: "
            f"expected number, received {type(fire_at).__name__}"
        )
    return entry


def load_all_or_nothing(root: Path) -> list:
    """The broken behavior: first invalid entry rejects the whole registry."""
    entries = []
    for path in sorted((root / "tasks").glob("*.json")):
        entry = json.loads(path.read_text(encoding="utf-8"))
        try:
            entries.append(validate(entry))
        except ValueError as exc:
            raise RegistryRejected(str(exc)) from exc
    return entries


def load_quarantine(root: Path) -> tuple:
    """The guarded behavior: a bad entry is quarantined, the rest keep running."""
    loaded, quarantined = [], []
    for path in sorted((root / "tasks").glob("*.json")):
        entry = json.loads(path.read_text(encoding="utf-8"))
        try:
            loaded.append(validate(entry))
        except ValueError:
            quarantined.append(entry.get("id", path.name))
    return loaded, quarantined


def parity_alarm(on_disk: int, loaded: int) -> bool:
    """The detection guard: any gap between disk and memory is an alarm, not silence."""
    return on_disk != loaded


def tick(tasks: list, now_ms: int) -> list:
    """One scheduler tick: fire every enabled task whose fireAt has passed."""
    return [t for t in tasks if t["enabled"] and t["fireAt"] <= now_ms]


def run_mode(root: Path, mode: str) -> dict:
    on_disk = len(list((root / "tasks").glob("*.json")))
    if mode == "all-or-nothing":
        try:
            loaded = load_all_or_nothing(root)
        except RegistryRejected:
            loaded = []  # what the real system does: registry fails to load, app runs on
        quarantined = []
    else:
        loaded, quarantined = load_quarantine(root)
    fired = tick(loaded, NOW_MS)
    return {
        "on_disk": on_disk,
        "loaded": len(loaded),
        "fired": len(fired),
        "quarantined": len(quarantined),
        "alarm": parity_alarm(on_disk, len(loaded)),
    }


def main() -> int:
    results = {}
    with tempfile.TemporaryDirectory() as tmp:
        broken_root = Path(tmp) / "broken"
        write_registry(broken_root, with_bad_entry=True)
        results["all-or-nothing"] = run_mode(broken_root, "all-or-nothing")
        results["quarantine"] = run_mode(broken_root, "quarantine")

        healthy_root = Path(tmp) / "healthy"
        write_registry(healthy_root, with_bad_entry=False)
        results["healthy"] = run_mode(healthy_root, "quarantine")

    aon, qua, hea = results["all-or-nothing"], results["quarantine"], results["healthy"]
    # In the real system there IS no parity guard in this mode: the drop is silent.
    # test_registry_guard.py shows what the guard would say (alarm(6,0)=True).
    print(
        f"mode=all-or-nothing  on_disk={aon['on_disk']} loaded={aon['loaded']} "
        f"fired={aon['fired']} dropped={aon['on_disk'] - aon['loaded']} "
        f"alarm=none (SILENT)"
    )
    print(
        f"mode=quarantine      on_disk={qua['on_disk']} loaded={qua['loaded']} "
        f"fired={qua['fired']} quarantined={qua['quarantined']} "
        f"alarm={'PARITY on_disk=%d loaded=%d' % (qua['on_disk'], qua['loaded']) if qua['alarm'] else 'none'}"
    )
    print(
        f"mode=healthy         on_disk={hea['on_disk']} loaded={hea['loaded']} "
        f"fired={hea['fired']} quarantined={hea['quarantined']} "
        f"alarm={'PARITY' if hea['alarm'] else 'none'}"
    )

    ok = (
        aon["loaded"] == 0 and aon["fired"] == 0            # the bug: total silent loss
        and qua["loaded"] == 5 and qua["fired"] == 5        # the guard: rest keeps running
        and qua["quarantined"] == 1 and qua["alarm"]        # ...and the drop is VISIBLE
        and hea["loaded"] == 6 and hea["fired"] == 6 and not hea["alarm"]
    )
    print("repro:", "OK - mechanism demonstrated" if ok else "FAIL - model drifted from the case doc")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
