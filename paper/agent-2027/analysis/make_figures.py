# -*- coding: utf-8 -*-
"""make_figures.py -- draw figures/*.pdf from data/aggregates-agent-2027.json (no raw data needed).
Written 2026-11-08, Claude Opus 5.5, session Z60039, node laptop. rail: claude."""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.realpath(__file__)); FIG = os.path.join(HERE, "..", "figures"); os.makedirs(FIG, exist_ok=True)
A = json.load(open(os.path.join(HERE, "..", "data", "aggregates-agent-2027.json"), encoding="utf-8"))
plt.rcParams.update({"font.size": 8, "font.family": "serif", "axes.spines.top": False, "axes.spines.right": False})

w = A["weekly"]; W = w["weeks"]; x = range(len(W)); lab = [d[5:].replace("-", "/") for d in W]
fig, ax = plt.subplots(figsize=(3.5, 2.0))
ax.bar(x, w["session"], color="0.75", label="written by agent sessions")
ax.bar(x, w["robot"], bottom=w["session"], color="0.25", label="filed by the self-healing watchdog (could not heal)")
ax.set_xticks(list(x)); ax.set_xticklabels(lab, rotation=45); ax.set_ylabel("journal lines per ISO week")
ax.legend(fontsize=6, frameon=False, loc="upper left")
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_weekly.pdf")); plt.close(fig)

if "audit" in A:
    au = A["audit"]; G = ["SCHEDULE", "DISPATCH", "VERIFY"]
    sil = [au["cp_by_group_silent"][g][0] for g in G]; dec = [au["cp_by_group_silent"][g][1] for g in G]
    tot = [au["cp_by_group"][g] for g in G]
    loud = [d - s for d, s in zip(dec, sil)]; unc = [t - d for t, d in zip(tot, dec)]
    fig, ax = plt.subplots(figsize=(3.5, 1.9))
    y = range(len(G))
    ax.barh(y, sil, color="0.2", label="silent")
    ax.barh(y, loud, left=sil, color="0.6", label="loud")
    ax.barh(y, unc, left=[a + b for a, b in zip(sil, loud)], color="0.9", edgecolor="0.6", lw=0.5, label="unclear")
    ax.set_yticks(list(y)); ax.set_yticklabels(["what is scheduled", "what is launched", "whether it worked"])
    ax.invert_yaxis(); ax.set_xlabel("sampled control-plane lines (majority label)")
    ax.legend(fontsize=6, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.38), ncol=3)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_audit.pdf")); plt.close(fig)
print("figures ok")
