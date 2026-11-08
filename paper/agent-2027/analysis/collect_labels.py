# -*- coding: utf-8 -*-
"""collect_labels.py -- parse rater outputs (prompts/out*.txt, llm_ask --with-rail format) into data/labels_<rail>.jsonl.
Keeps only objects whose id is in the audit sample and whose codes are in the codebook; the first valid label per
(rail, id) wins, so a re-run batch never overwrites an earlier answer. Prints coverage per rail.
Written 2026-11-08, Claude Opus 5.5, session Z60039. rail: claude."""
import glob, json, os, re, collections
HERE = os.path.dirname(os.path.realpath(__file__)); ROOT = os.path.join(HERE, "..")
IDS = {json.loads(l)["i"] for l in open(os.path.join(ROOT, "data", "audit_sample.jsonl"), encoding="utf-8")}
OK = {"g": {"SCHEDULE", "DISPATCH", "VERIFY", "OTHER"}, "s": {"SILENT", "LOUD", "UNCLEAR"}, "m": {"M1", "M2", "M3", "M4", "M5", "NONE"}}
labels = collections.defaultdict(dict)
for f in sorted(glob.glob(os.path.join(ROOT, "prompts", "out*.txt"))):
    fm = re.match(r"out_(\w+?)_s\d+\.txt$", os.path.basename(f))
    rail = fm.group(1) if fm else None
    for line in open(f, encoding="utf-8", errors="replace"):
        h = re.match(r"^=== (\w+) ===", line)
        if h:
            if not fm:   # only multi-rail outputs carry headers; a header inside a one-rail file is ignored
                rail = h.group(1)
            continue
        for obj in re.findall(r"\{[^{}]*\}", line):
            try:
                x = json.loads(obj)
            except ValueError:
                continue
            if rail and x.get("i") in IDS and all(str(x.get(k, "")).upper() in OK[k] for k in OK):
                labels[rail].setdefault(x["i"], {"i": x["i"], **{k: str(x[k]).upper() for k in OK}})
for old in glob.glob(os.path.join(ROOT, "data", "labels_*.jsonl")):
    os.remove(old)   # no stale rater file may survive into the audit
for rail, d in labels.items():
    with open(os.path.join(ROOT, "data", "labels_%s.jsonl" % rail), "w", encoding="utf-8") as fo:
        for i in sorted(d):
            fo.write(json.dumps(d[i]) + "\n")
    print(rail, len(d), "of", len(IDS))
