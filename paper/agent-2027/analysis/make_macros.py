# -*- coding: utf-8 -*-
"""make_macros.py -- turn data/aggregates-agent-2027.json into numbers.tex (LaTeX macros).
Every numeric claim in main.tex is a macro defined here, so a number cannot appear in the paper
without a field in the JSON. Pattern reused from agent-fleet/cain-2027/analysis/make_macros.py.
Written 2026-11-08, Claude Opus 5.5, session Z60039, node laptop. rail: claude."""
import json, os
HERE = os.path.dirname(os.path.realpath(__file__))
A = json.load(open(os.path.join(HERE, "..", "data", "aggregates-agent-2027.json"), encoding="utf-8"))
out = []
WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine"}


def m(name, val):
    if isinstance(val, float):
        val = "%.1f" % val
        if val.endswith(".0"):
            val = val[:-2]
    if isinstance(val, int):
        val = "{:,}".format(val)
    out.append("\\newcommand{\\%s}{%s\\xspace}" % (name, val))


def pct(name, trip):
    e, lo, hi = trip
    m(name, "%.1f\\%%" % e); m(name + "CI", "[%.1f, %.1f]" % (lo, hi))


def mci(name, trip):
    e, lo, hi = trip
    m(name, ("%.1f" % e).rstrip("0").rstrip(".")); m(name + "CI", "[%s, %s]" % (("%.1f" % lo).rstrip("0").rstrip("."), ("%.1f" % hi).rstrip("0").rstrip(".")))


sn, ro, se, rc, w = A["snapshot"], A["robot"], A["session"], A["recovered"], A["weekly"]
m("winLo", "4 September"); m("winHi", "7 November 2026"); m("nDays", sn["days"]); m("nNodes", sn["nodes"])
m("nNodesWord", WORDS.get(sn["nodes"], str(sn["nodes"])))
m("nWindow", sn["records_window"]); m("nShards", sn["shards"])
m("nRobot", ro["lines"]); pct("pRobot", ro["share_of_window"]); m("nRobotTargets", ro["targets"])
m("nRobotRunbookNone", ro["runbook_none"]); pct("pRobotRunbookNone", ro["runbook_none_pct"])
q = ro["repeats_quartiles"]; m("robotRepQOne", int(q[0])); m("robotRepQThree", int(q[2]))
mci("robotRepMedian", ro["repeats_median_ci"]); m("robotRepMax", ro["repeats_max"])
m("robotTargetsGeThree", ro["targets_ge3"]); m("robotTargetsGeTen", ro["targets_ge10"])
mci("robotSpanMedian", ro["span_days_median_ci"]); mci("robotPerDay", ro["per_day_median_ci"]); m("robotDays", ro["days_with_lines"])
m("nSession", se["lines"]); m("nNames", se["class_names"]); m("nSingleNames", se["singleton_names"]); pct("pSingleNames", se["singleton_names_pct"])
m("nNamesGeThree", se["names_ge3"]); m("nLinesNamesGeThree", se["lines_in_names_ge3"]); pct("pLinesNamesGeThree", se["lines_in_names_ge3_pct"])
m("nameMax", se["lines_per_name_max"])
if "families_hit" in se:
    m("famMap", se["family_map_size"]); m("famLines", se["lines_with_family"]); pct("pFamLines", se["lines_with_family_pct"])
    m("famHit", se["families_hit"]); m("famGeThree", se["families_ge3"]); m("famHidden", se["families_ge3_hidden_by_names"])
    m("famLinesGeThree", se["lines_in_families_ge3"]); pct("pFamLinesGeThree", se["lines_in_families_ge3_pct"])
    m("famOnlyLines", se["lines_recurring_family_only"]); m("eitherLines", se["lines_recurring_either"])
    m("famNamesMedian", float(se["names_per_family_median"])); m("famNamesMax", se["names_per_family_max"])
m("nRecovered", rc["records"]); m("nRecoveredWindow", rc["records_window"]); m("nRecoveredRobot", rc["robot_window"])
m("nWeeks", len(w["weeks"]))
import datetime as _dt
m("firstRecord", str(int(sn["first_record"][8:10])) + " " + _dt.date.fromisoformat(sn["first_record"]).strftime("%B"))
m("nAnchorLines", sn["by_role"].get("anchor", 0))
_c = A.get("cases", {})
m("cTwelveSilentDays", (_dt.date.fromisoformat(_c["c12_found_on"]["value"]) - _dt.date.fromisoformat(_c["c12_evacuated_on"]["value"])).days)
mk = w["mk_session_per_node"]; m("mkTau", "%.2f" % mk["tau"]); m("mkP", "< 0.001" if mk["p"] < 0.001 else "%.3f" % mk["p"])
if "audit" in A:
    au = A["audit"]
    m("auSample", au["sample"]); m("auComplete", au["complete"]); m("auRails", len(au["rails"]))
    m("auDecided", au["group_decided"]); m("auCP", au["control_plane"]); pct("pAuCP", au["control_plane_pct"])
    m("auSched", au["cp_by_group"]["SCHEDULE"]); m("auDisp", au["cp_by_group"]["DISPATCH"]); m("auVerify", au["cp_by_group"]["VERIFY"])
    m("auSilent", au["cp_silent"]); m("auSilentDecided", au["cp_silent_decided"]); pct("pAuSilent", au["cp_silent_pct"])
    m("auOtherSilent", au["other_silent"]); m("auOtherDecided", au["other_silent_decided"]); pct("pAuOtherSilent", au["other_silent_pct"])
    m("auMechAny", au["cp_mech_any"]); pct("pAuMechAny", au["cp_mech_any_pct"])
    for k in ("M1", "M2", "M3", "M4", "M5", "NONE"):
        m("auMech" + {"M1": "One", "M2": "Two", "M3": "Three", "M4": "Four", "M5": "Five", "NONE": "None"}[k], au["cp_mech"][k])
    for key, nm in (("g", "G"), ("s", "S"), ("m", "M")):
        m("kappaF" + nm, "%.2f" % au["fleiss_" + key] if au["fleiss_" + key] is not None else "n/a")
        m("kappaMin" + nm, "%.2f" % au["cohen_" + key + "_min"]); m("kappaMax" + nm, "%.2f" % au["cohen_" + key + "_max"])
        m("noMaj" + nm, au["no_majority_" + key])
    m("auCPBoundLo", "%.1f\\%%" % au["control_plane_bounds"][0]); m("auCPBoundHi", "%.1f\\%%" % au["control_plane_bounds"][1])
    m("auMechDecided", au["cp_mech_decided"]); m("auUnresolved", au["unresolved_group"])
    dd = au["silent_diff"]; m("silDiff", "%.1f" % dd[0]); m("silDiffCI", "[%.1f, %.1f]" % (dd[1], dd[2]))
    lo, hi = au["cp_lines_est"][1], au["cp_lines_est"][2]
    m("cpEstLo", lo); m("cpEstHi", hi)
for k, f in A.get("cases", {}).items():
    if k.startswith("_"):
        continue
    v = f["value"]
    NUM = {"c1": "COne", "c2": "CTwo", "c3": "CThree", "c4": "CFour", "c5": "CFive", "c6": "CSix", "c7": "CSeven",
           "c8": "CEight", "c9": "CNine", "c10": "CTen", "c11": "CEleven", "c12": "CTwelve", "audit0822": "Aug"}
    parts = k.split("_")
    name = "cf" + NUM.get(parts[0], parts[0].capitalize()) + "".join(p.capitalize() for p in parts[1:])
    assert name.isalpha(), name
    if isinstance(v, str) and len(v) == 10 and v[4] == "-" and v[7] == "-":
        import datetime as _d2
        v = str(int(v[8:])) + " " + _d2.date.fromisoformat(v).strftime("%B")   # 2026-10-18 -> 18 October
    m(name, v)
open(os.path.join(HERE, "..", "numbers.tex"), "w", encoding="utf-8").write("\\usepackage{xspace}\n" + "\n".join(out) + "\n")
print("macros:", len(out))
