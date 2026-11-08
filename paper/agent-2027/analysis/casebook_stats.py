# -*- coding: utf-8 -*-
"""casebook_stats.py -- aggregate-only statistics for the AGENT@ICSE 2027 version of the
control-plane casebook ("Silent by construction").

Passport
  input  : the fleet breakage journal shards <vault>/_machine-bus/_breakage/breakage__from-<node>.jsonl
           (append-only, one record per observed failure, written through selfheal.py journal);
           optional rater labels data/labels_<rail>.jsonl produced from data/audit_sample.jsonl;
           data/case_facts.json (numbers quoted inside the eleven cases, each with its source).
  output : data/aggregates-agent-2027.json (numbers only: no record text, no host names).
           `sample` mode writes data/audit_sample.jsonl (sanitised text of a seeded random sample).
  callers: build.sh of this folder; make_macros.py and make_figures.py read the JSON.
  breaks : if a shard schema changes (fields id/date/node/class/text) the loader raises.
  rail   : claude (this script, no LLM calls); the rater labels come from glm, grok, mistral via llm_ask.py.
Written 2026-11-08 by Claude Opus 5.5 (session Z60039, node laptop), method reused from
agent-fleet/cain-2027/analysis/fleet_cain_stats.py (Wilson, bootstrap, Mann-Kendall helpers copied).

Usage: python casebook_stats.py [sample]
"""
import glob, json, os, re, sys, math, random, collections, datetime as dt
import numpy as np
from scipy.stats import norm

VAULT = os.environ.get("OBSIDIAN_VAULT", ".")
SHARDS = os.environ.get("BREAKAGE_SHARDS", os.path.join(VAULT, "_machine-bus", "_breakage"))
HERE = os.path.dirname(os.path.realpath(__file__))
DATA = os.path.join(HERE, "..", "data")
WIN_LO, WIN_HI = "2026-09-04", "2026-11-07"   # first shard record .. last full day before the snapshot
SAMPLE_N = 200
SEED = 20261108
PRIVATE = json.load(open(os.environ.get("CASEBOOK_PRIVATE", os.path.join(os.path.dirname(os.path.realpath(__file__)), "private_patterns.json")), encoding="utf-8")) if os.path.exists(os.environ.get("CASEBOOK_PRIVATE", os.path.join(os.path.dirname(os.path.realpath(__file__)), "private_patterns.json"))) else {"role": {}, "hosts": "(?!x)x", "names": "(?!x)x"}
ROLE = PRIVATE["role"]   # host -> role label; the real map is private
ROBOT_MARK = "робот-сторож не смог вылечить"
# machines whose journal legitimately starts late; anything else late is treated as a vanished shard by the test
KNOWN_LATE = {"workstation": "joined the fleet journal on 2026-09-30 (its first record); anchor bus_guard log shows no evacuation of its shard"}
RATERS = ["gemini", "glm", "mistral"]   # predeclared panel; a fourth labels file is ignored, a missing one fails the audit
GROUPS = ["SCHEDULE", "DISPATCH", "VERIFY", "OTHER"]
SILENT = ["SILENT", "LOUD", "UNCLEAR"]
MECH = ["M1", "M2", "M3", "M4", "M5", "NONE"]


def newcombe_diff(k1, n1, k2, n2, z=1.96):
    """Difference p1-p2 in percentage points with Newcombe's hybrid score interval (method 10)."""
    if n1 == 0 or n2 == 0:
        return None
    p1, p2 = k1 / n1, k2 / n2
    def wl(k, n):
        p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
        h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
        return c - h, c + h
    l1, u1 = wl(k1, n1); l2, u2 = wl(k2, n2); d = p1 - p2
    lo = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2); hi = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return [round(100 * d, 1), round(100 * lo, 1), round(100 * hi, 1)]


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * p, 1), round(100 * (c - h), 1), round(100 * (c + h), 1)]


def boot(xs, fn, B=2000, seed=SEED):
    rng = np.random.default_rng(seed)
    xs = np.asarray(xs, float)
    if len(xs) == 0:
        return None
    est = fn(xs); bs = [fn(rng.choice(xs, len(xs))) for _ in range(B)]
    return [round(float(est), 1), round(float(np.percentile(bs, 2.5)), 1), round(float(np.percentile(bs, 97.5)), 1)]


def mann_kendall(x):
    x = list(x); n = len(x); s = 0
    if n < 3:
        return {"n": n, "S": 0, "z": 0.0, "p": 1.0, "tau": 0.0}
    for i in range(n - 1):
        for j in range(i + 1, n):
            s += np.sign(x[j] - x[i])
    ties = collections.Counter(x).values()   # tie-corrected variance (Kendall 1975)
    var = (n * (n - 1) * (2 * n + 5) - sum(t * (t - 1) * (2 * t + 5) for t in ties)) / 18.0
    z = (s - 1) / math.sqrt(var) if s > 0 else (s + 1) / math.sqrt(var) if s < 0 else 0.0
    p = 2 * (1 - norm.cdf(abs(z)))
    return {"n": n, "S": int(s), "z": round(float(z), 2), "p": round(float(p), 4), "tau": round(float(s / (n * (n - 1) / 2)), 2)}


def cohen(a, b, cats):
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return round((po - pe) / (1 - pe), 2) if pe < 1 else 1.0


def fleiss(table, cats):
    """table: list of label lists (one list of rater labels per item, equal length)."""
    N = len(table)
    if N == 0:
        return None
    m = len(table[0])
    P = []; pj = collections.Counter()
    for labs in table:
        c = collections.Counter(labs); pj.update(c)
        P.append((sum(v * v for v in c.values()) - m) / (m * (m - 1)))
    Pbar = sum(P) / N; Pe = sum((pj[c] / (N * m)) ** 2 for c in cats)
    return round((Pbar - Pe) / (1 - Pe), 2) if Pe < 1 else 1.0


def wk(d):
    d = dt.date.fromisoformat(d[:10]); return (d - dt.timedelta(days=d.weekday())).isoformat()


def full_weeks(lo, hi):
    d = dt.date.fromisoformat(lo); h = dt.date.fromisoformat(hi)
    while d.weekday() != 0:
        d += dt.timedelta(days=1)
    w = []
    while d + dt.timedelta(days=6) <= h:
        w.append(d.isoformat()); d += dt.timedelta(days=7)
    return w


def load():
    rows, seen = [], {}
    # data/recovered holds the hub shard that a bus size guard evacuated to a non-synced folder on
    # 2026-10-18 (copied back from the anchor 2026-11-08, sha256 8dbf6e49...); ids dedupe any overlap
    files = sorted(glob.glob(os.path.join(SHARDS, "breakage__from-*.jsonl"))) + \
        sorted(glob.glob(os.path.join(DATA, "recovered", "breakage__from-*.jsonl")))
    if not files:
        raise SystemExit("no shards under %s" % SHARDS)
    for f in files:
        for line in open(f, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            for k in ("id", "date", "node", "class", "text"):
                if k not in r:
                    raise ValueError("shard schema changed: %s lacks %s" % (f, k))
            if r["id"] in seen:
                if r["text"] != seen[r["id"]]:
                    CONFLICTS.append(r["id"])
                continue
            r["_src"] = "recovered" if (os.sep + "recovered" + os.sep in os.path.normpath(f) or "__archive-20261018" in f) else "bus"
            seen[r["id"]] = r["text"]; rows.append(r)
    return rows, len(files)


CONFLICTS = []
NAMES = re.compile(PRIVATE["names"], re.I)


def sanitise(text):
    t = text
    for h, role in ROLE.items():
        t = re.sub(re.escape(h), role, t, flags=re.I)
    t = re.sub(PRIVATE["hosts"], "node", t, flags=re.I)
    t = NAMES.sub("operator", t)
    t = re.sub(r"-?100\d{7,}", "<chat>", t)
    t = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "<email>", t)
    t = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "<ip>", t)
    t = re.sub(r"\\\\[^\s|,;)]+", "<path>", t)
    t = re.sub(r"\bgithub_pat_\w{10,}|\beyJ[\w-]{10,}\.[\w-]+", "<secret>", t)
    t = re.sub(r"\+\d[\d ()-]{8,}\d", "<phone>", t)
    t = re.sub(r"https?://[^\s|,;)]*[?&](?:token|key|sig)=[^\s|,;)]*", "<url>", t)
    t = re.sub(r"(?:/Volumes|/mnt)/[^\s|,;)]*", "<path>", t)
    t = re.sub(r"(?i)bearer\s+[A-Za-z0-9._-]{10,}", "<secret>", t)
    t = re.sub(r"[A-Za-z]:[\\/][^\s|,;)]*", "<path>", t)
    t = re.sub(r"(?:/Users|/home|/root)/[^\s|,;)]*", "<path>", t)
    t = re.sub(r"\b(sk|ghp|gho|xox[bp])[-_][A-Za-z0-9_-]{8,}", "<secret>", t)
    return t[:600]


def fields(text):
    parts = [p.strip() for p in text.strip().strip("|").split("|")]
    return parts  # date, class, what, conditions, parts, guess, count, status


def majority(labs):
    c = collections.Counter(labs).most_common()
    return c[0][0] if c[0][1] >= 2 else None


def main():
    rows, nshards = load()
    win = [r for r in rows if WIN_LO <= r["date"][:10] <= WIN_HI]
    robot = [r for r in win if ROBOT_MARK in r["text"]]
    sess = [r for r in win if ROBOT_MARK not in r["text"]]
    os.makedirs(DATA, exist_ok=True)

    if len(sys.argv) > 1 and sys.argv[1] == "sample":
        rng = random.Random(SEED)
        pick = rng.sample(sorted(sess, key=lambda r: r["id"]), SAMPLE_N)
        with open(os.path.join(DATA, "audit_sample.jsonl"), "w", encoding="utf-8") as fo:
            for r in pick:
                f = fields(r["text"])
                fo.write(json.dumps({"i": r["id"], "cls": sanitise(r["class"]), "what": sanitise(f[2] if len(f) > 2 else r["text"]),
                                     "conditions": sanitise(f[3] if len(f) > 3 else ""), "cause": sanitise(f[5] if len(f) > 5 else "")},
                                    ensure_ascii=False) + "\n")
        print("sample written:", SAMPLE_N); return

    A = {"snapshot": {"window": [WIN_LO, WIN_HI], "shards": nshards, "records_all": len(rows), "records_window": len(win),
                      "first_record": min(r["date"][:10] for r in rows), "last_record": max(r["date"][:10] for r in rows)}}
    nodes = collections.Counter(ROLE.get(r["node"], "other") for r in win)
    A["snapshot"]["nodes"] = len(nodes); A["snapshot"]["by_role"] = dict(nodes)
    # coverage per role: a shard that vanished (case C12) shows up as a late first day, not as a smaller total
    A["snapshot"]["known_late"] = KNOWN_LATE
    A["snapshot"]["first_day_by_role"] = {k: min(r["date"][:10] for r in win if ROLE.get(r["node"], "other") == k) for k in nodes}
    A["snapshot"]["days"] = (dt.date.fromisoformat(WIN_HI) - dt.date.fromisoformat(WIN_LO)).days + 1

    # ---- stratum 1: lines filed by the self-healing watchdog it could not heal ----
    tgt = collections.Counter()
    first, last = {}, {}
    runbook_none = 0; unparsed = 0
    for r in robot:
        m = re.search(ROBOT_MARK + r": ([^|]+)", r["text"])
        if not m:
            unparsed += 1; continue
        t = m.group(1).strip()
        tgt[t] += 1; d = r["date"][:10]
        first[t] = min(first.get(t, d), d); last[t] = max(last.get(t, d), d)
        if "runbook=нет" in r["text"]:
            runbook_none += 1
    reps = list(tgt.values())
    spans = [(dt.date.fromisoformat(last[t]) - dt.date.fromisoformat(first[t])).days + 1 for t in tgt]
    rdays = sorted({r["date"][:10] for r in robot})
    perday = collections.Counter(r["date"][:10] for r in robot)
    allday = []
    if rdays:
        d0 = dt.date.fromisoformat(rdays[0])
        while d0.isoformat() <= WIN_HI:
            allday.append(perday.get(d0.isoformat(), 0)); d0 += dt.timedelta(days=1)
    A["robot"] = {"lines": len(robot), "first_day": rdays[0] if rdays else None, "days_with_lines": len(rdays),
                  "per_day_median_ci": boot(allday, np.median), "unparsed_target": unparsed, "id_conflicts": len(CONFLICTS), "share_of_window": wilson(len(robot), len(win)), "targets": len(tgt),
                  "nodes": len({r["node"] for r in robot}), "runbook_none": runbook_none,
                  "runbook_none_pct": wilson(runbook_none, len(robot)),
                  "repeats_median_ci": boot(reps, np.median), "repeats_quartiles": [float(np.percentile(reps, q)) for q in (25, 50, 75)] if reps else None, "repeats_max": max(reps) if reps else 0,
                  "targets_ge3": sum(1 for v in reps if v >= 3), "targets_ge10": sum(1 for v in reps if v >= 10),
                  "span_days_median_ci": boot(spans, np.median), "repeats_sorted": sorted(reps, reverse=True)}

    # ---- stratum 2: lines written by agent sessions ----
    names = collections.Counter(r["class"] for r in sess)
    single = sum(1 for v in names.values() if v == 1)
    ge3_names = [k for k, v in names.items() if v >= 3]
    A["session"] = {"lines": len(sess), "class_names": len(names), "singleton_names": single,
                    "singleton_names_pct": wilson(single, len(names)),
                    "names_ge3": len(ge3_names), "lines_in_names_ge3": sum(names[k] for k in ge3_names),
                    "lines_in_names_ge3_pct": wilson(sum(names[k] for k in ge3_names), len(sess)),
                    "lines_per_name_max": max(names.values()) if names else 0}
    # family view: the fleet's curated synonym map (prior_art.py FAMILIES), applied to class + text
    if True:   # the family map is required: an import failure must stop the build, not drop a paper number
        import io, contextlib
        sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".claude", "scripts"))
        with contextlib.redirect_stdout(io.StringIO()):
            import prior_art
        fam = collections.Counter(); hit = 0; fam_names = collections.defaultdict(set)
        for r in sess:
            fs = prior_art.families_of(r["class"] + " " + r["text"])
            if fs:
                hit += 1
            for f in fs:
                fam[f] += 1; fam_names[f].add(r["class"])
        ge3f = [f for f, v in fam.items() if v >= 3]
        A["session"]["family_map_size"] = len(prior_art.FAMILIES)
        A["session"]["lines_with_family"] = hit; A["session"]["lines_with_family_pct"] = wilson(hit, len(sess))
        A["session"]["families_hit"] = len(fam); A["session"]["families_ge3"] = len(ge3f)
        A["session"]["names_per_family_median"] = float(np.median([len(fam_names[f]) for f in fam])) if fam else 0
        A["session"]["names_per_family_max"] = max(len(fam_names[f]) for f in fam) if fam else 0
        # families whose every member name is below the threshold, i.e. recurrence invisible to an exact-name counter
        hidden = [f for f in ge3f if all(names[n] < 3 for n in fam_names[f])]
        A["session"]["families_ge3_hidden_by_names"] = len(hidden)
        # benchmark: lines that sit in a recurring unit (>=3 lines) under each detector
        fam_lines_ge3 = sum(1 for r in sess if any(f in ge3f for f in prior_art.families_of(r["class"] + " " + r["text"])))
        A["session"]["lines_in_families_ge3"] = fam_lines_ge3
        A["session"]["lines_in_families_ge3_pct"] = wilson(fam_lines_ge3, len(sess))
        both = sum(1 for r in sess if names[r["class"]] >= 3 and any(f in ge3f for f in prior_art.families_of(r["class"] + " " + r["text"])))
        A["session"]["lines_recurring_either"] = sum(1 for r in sess if names[r["class"]] >= 3) + fam_lines_ge3 - both
        A["session"]["lines_recurring_family_only"] = fam_lines_ge3 - both

    # ---- weekly series (full ISO weeks only) ----
    W = full_weeks(WIN_LO, WIN_HI)
    rw = collections.Counter(wk(r["date"]) for r in robot); sw = collections.Counter(wk(r["date"]) for r in sess)
    act = collections.defaultdict(set)
    for r in sess:
        act[wk(r["date"])].add(r["node"].upper())
    A["weekly"] = {"weeks": W, "robot": [rw[w] for w in W], "session": [sw[w] for w in W],
                   "session_active_nodes": [len(act[w]) for w in W],
                   "session_per_active_node": [round(sw[w] / max(1, len(act[w])), 1) for w in W]}
    _rate = [sw[w] / max(1, len(act[w])) for w in W]   # unrounded for the trend test
    A["recovered"] = {"records": sum(1 for r in rows if r.get("_src") == "recovered"),
                      "records_window": sum(1 for r in win if r.get("_src") == "recovered"),
                      "robot_window": sum(1 for r in robot if r.get("_src") == "recovered")}
    A["weekly"]["mk_session_per_node"] = mann_kendall(_rate)

    # ---- rater audit of a random sample of session lines ----
    samp = [json.loads(l) for l in open(os.path.join(DATA, "audit_sample.jsonl"), encoding="utf-8")] if os.path.exists(os.path.join(DATA, "audit_sample.jsonl")) else []
    labs = {}
    for f in sorted(glob.glob(os.path.join(DATA, "labels_*.jsonl"))):
        rail = os.path.basename(f)[7:-6]; d = {}
        for l in open(f, encoding="utf-8"):
            if l.strip():
                x = json.loads(l); d[x["i"]] = x
        labs[rail] = d
    if samp:
        missing = [r for r in RATERS if r not in labs]
        if missing:
            raise SystemExit("audit: rater labels missing for %s" % missing)
        stray = [i for r in RATERS for i in labs[r] if i not in {s_["i"] for s_ in samp}]
        if stray:
            raise SystemExit("audit: %d labels are not in the current sample" % len(stray))
        rails = RATERS; ids = [s["i"] for s in samp if all(s["i"] in labs[r] for r in rails)]
        import hashlib
        au = {"sample_sha256": hashlib.sha256(open(os.path.join(DATA, "audit_sample.jsonl"), "rb").read()).hexdigest(),
              "codebook_sha256": hashlib.sha256(open(os.path.join(HERE, "..", "prompts", "codebook.md"), "rb").read()).hexdigest(),
              "sample": len(samp), "rails": rails, "complete": len(ids), "coverage": {r: sum(1 for s_ in samp if s_["i"] in labs[r]) for r in rails}}
        for key, cats in (("g", GROUPS), ("s", SILENT), ("m", MECH)):
            table = [[labs[r][i][key] for r in rails] for i in ids]
            au["fleiss_" + key] = fleiss(table, cats) if len(rails) >= 3 else None
            pairs = []
            for a in range(len(rails)):
                for b in range(a + 1, len(rails)):
                    pairs.append(cohen([t[a] for t in table], [t[b] for t in table], cats))
            au["cohen_" + key + "_min"] = min(pairs); au["cohen_" + key + "_max"] = max(pairs)
            maj = [majority(t) for t in table]
            au["no_majority_" + key] = sum(1 for m in maj if m is None)
            au["dist_" + key] = dict(collections.Counter(m or "NOMAJ" for m in maj))
        g = [majority([labs[r][i]["g"] for r in rails]) for i in ids]
        s = [majority([labs[r][i]["s"] for r in rails]) for i in ids]
        m = [majority([labs[r][i]["m"] for r in rails]) for i in ids]
        cp = [k for k, x in enumerate(g) if x in ("SCHEDULE", "DISPATCH", "VERIFY")]
        decided = [k for k, x in enumerate(g) if x is not None]
        au["control_plane"] = len(cp); au["group_decided"] = len(decided)
        au["control_plane_pct"] = wilson(len(cp), len(decided))
        # bounds over the complete set: undecided items counted as not control plane / as control plane
        # bounds over the FULL random sample: every unresolved item (no label set or no majority) counted out, then in
        au["control_plane_bounds"] = [round(100 * len(cp) / len(samp), 1), round(100 * (len(cp) + len(samp) - len(decided)) / len(samp), 1)]
        au["unresolved_group"] = len(samp) - len(decided)
        au["cp_by_group"] = {x: sum(1 for k in cp if g[k] == x) for x in ("SCHEDULE", "DISPATCH", "VERIFY")}
        sd = [k for k in cp if s[k] in ("SILENT", "LOUD")]
        au["cp_silent"] = sum(1 for k in sd if s[k] == "SILENT"); au["cp_silent_decided"] = len(sd)
        au["cp_silent_pct"] = wilson(au["cp_silent"], len(sd))
        nd = [k for k, x in enumerate(g) if x == "OTHER" and s[k] in ("SILENT", "LOUD")]
        au["other_silent"] = sum(1 for k in nd if s[k] == "SILENT"); au["other_silent_decided"] = len(nd)
        au["other_silent_pct"] = wilson(au["other_silent"], len(nd))
        au["silent_diff"] = newcombe_diff(au["cp_silent"], au["cp_silent_decided"], au["other_silent"], len(nd))
        au["cp_mech"] = {x: sum(1 for k in cp if m[k] == x) for x in MECH}
        au["cp_mech_any"] = sum(1 for k in cp if m[k] in ("M1", "M2", "M3", "M4", "M5"))
        au["cp_mech_decided"] = sum(1 for k in cp if m[k] is not None)
        au["cp_mech_any_pct"] = wilson(au["cp_mech_any"], au["cp_mech_decided"])
        au["cp_by_group_silent"] = {x: [sum(1 for k in sd if g[k] == x and s[k] == "SILENT"), sum(1 for k in sd if g[k] == x)] for x in ("SCHEDULE", "DISPATCH", "VERIFY")}
        A["audit"] = au
        # population estimate of control-plane session lines
        A["audit"]["cp_lines_est"] = [round(len(sess) * v / 100) for v in au["control_plane_pct"]]

    # ---- numbers quoted inside the cases, each with its source ----
    cf = os.path.join(DATA, "case_facts.json")
    if os.path.exists(cf):
        A["cases"] = {k: ({"value": v["value"], "source": sanitise(v["source"])} if isinstance(v, dict) else v)
                      for k, v in json.load(open(cf, encoding="utf-8")).items()}

    json.dump(A, open(os.path.join(DATA, "aggregates-agent-2027.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("written", os.path.join(DATA, "aggregates-agent-2027.json"))


if __name__ == "__main__":
    main()
