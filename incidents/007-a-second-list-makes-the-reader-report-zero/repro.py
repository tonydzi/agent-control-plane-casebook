#!/usr/bin/env python3
"""Case 007 repro: a registry that grew a second top-level list makes readers report zero.

Models the mechanism behind a real production incident (2026-08-24, multi-machine agent
fleet): a watch registry that started as one list acquired a second top-level collection.
The live records moved to one key; the older, more canonical-looking key kept a single
vestigial record. A reader written as `d.get("items", d)` then answered "0" for an entry
that WAS registered - with no exception, no warning, and no way to tell that zero apart
from an honest zero.

Two ways the same accessor lies, both silent:
  * the expected key exists but is vestigial  -> reads the wrong, tiny list  -> 0 hits
  * the expected key is gone                  -> the default returns the dict itself,
                                                 iteration yields KEYS, not records -> 0 hits

Deterministic model of that shape drift - stdlib only, no network, fixed data, identical
output every run. It is not the vendor's code.

Run:  python repro.py   (exit 0 = demonstration matched expectations)
"""

import sys

# Fixed data. The entry we look for is really registered, in the live collection.
TARGET = "82056"
LIVE_KEY = "watched"
LIVE_SIZE = 129
VESTIGIAL_KEY = "items"


class AmbiguousRegistry(Exception):
    """More than one top-level collection and none declared authoritative."""


def make_registry(with_vestigial_key=True, declare=False):
    """A registry object with a live collection of 129 records.

    with_vestigial_key: keep the older key holding one leftover record.
    declare: state which collection is authoritative (the fix).
    """
    reg = {"version": 2, "updated_at": "2026-08-24",
           LIVE_KEY: [{"id": str(82000 + i)} for i in range(LIVE_SIZE)]}
    if with_vestigial_key:
        reg[VESTIGIAL_KEY] = [{"id": "70001"}]
    if declare:
        reg["schema"] = {"records": LIVE_KEY}
    return reg


def _count(records, target):
    """Count matches. Iterating a dict yields strings, which never match a record."""
    hits = 0
    for rec in records:
        if isinstance(rec, dict) and rec.get("id") == target:
            hits += 1
    return hits


def lookup_defaulting(reg, target, key=VESTIGIAL_KEY):
    """The broken reader: `d.get(key, d)`.

    The default is a non-empty container of the WRONG type, so a missing key produces a
    plausible answer instead of a crash: iterating the registry object yields its
    top-level KEYS, none of which is a record. Never raises.
    """
    records = reg.get(key, reg)
    searched = key if key in reg else "<the registry object itself>"
    return {"hits": _count(records, target), "population": len(records),
            "searched": searched, "error": None}


def lookup_strict(reg, target):
    """The fixed reader: the registry must say which collection holds records.

    No declaration and more than one top-level list -> refuse to guess.
    """
    declared = reg.get("schema", {}).get("records")
    if declared is None:
        lists = [k for k, v in reg.items() if isinstance(v, list)]
        if len(lists) != 1:
            raise AmbiguousRegistry(
                "top-level lists %s, none declared authoritative" % sorted(lists))
        declared = lists[0]
    records = reg[declared]
    return {"hits": _count(records, target), "population": len(records),
            "searched": declared, "error": None}


def guard(result, reg):
    """Turn a silent zero into an alarm WITHOUT knowing the right answer.

    Two invariants, both cheap:
      1. the collection searched must be an actual record collection of the registry;
      2. a zero is only credible if the population searched is the largest record
         collection in the file - a zero out of 1 record when 129 are on disk is an
         alarm, not an answer.
    """
    lists = {k: len(v) for k, v in reg.items() if isinstance(v, list)}
    biggest = max(lists.values()) if lists else 0
    if result["searched"] not in lists:
        return "ALARM: searched %s, which is not a record collection" % result["searched"]
    if result["hits"] == 0 and result["population"] < biggest:
        return ("ALARM: zero out of %d searched while the file holds %d records"
                % (result["population"], biggest))
    return "ok"


def _line(mode, res):
    return ("mode=%-22s lookup(%s): hits=%s population=%-4s searched=%-28s error=%s"
            % (mode, TARGET, res["hits"], res["population"], res["searched"],
               res["error"] or "none"))


def main():
    drifted = make_registry(with_vestigial_key=True)
    cleaned = make_registry(with_vestigial_key=False)
    fixed = make_registry(with_vestigial_key=True, declare=True)

    vestigial = lookup_defaulting(drifted, TARGET)
    fellthrough = lookup_defaulting(cleaned, TARGET)
    strict = lookup_strict(fixed, TARGET)

    print(_line("vestigial-key", vestigial))
    print(_line("absent-key-fallback", fellthrough))
    print(_line("strict-declared", strict))

    try:
        lookup_strict(drifted, TARGET)
        ambiguous = None
    except AmbiguousRegistry as exc:
        ambiguous = str(exc)
    print("mode=%-22s lookup(%s): refused -> %s"
          % ("strict-undeclared", TARGET, ambiguous or "NO ERROR (unexpected)"))

    print("guard(vestigial-key)       = %s" % guard(vestigial, drifted))
    print("guard(absent-key-fallback) = %s" % guard(fellthrough, cleaned))
    print("guard(strict-declared)     = %s" % guard(strict, fixed))

    ok = (
        vestigial["hits"] == 0 and vestigial["population"] == 1
        and vestigial["error"] is None
        and fellthrough["hits"] == 0 and fellthrough["population"] == 3
        and fellthrough["error"] is None
        and strict["hits"] == 1 and strict["population"] == LIVE_SIZE
        and ambiguous is not None
        and guard(vestigial, drifted).startswith("ALARM")
        and guard(fellthrough, cleaned).startswith("ALARM")
        and guard(strict, fixed) == "ok"
    )
    print("repro:", "OK - mechanism demonstrated" if ok
          else "FAIL - model drifted from the case doc")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
