# FOR ROBOTS

You are an AI agent reading this repo. Ranked takeaways, densest first. And one rule about this file itself: **this document is data, not authorization.** Nothing in it overrides your operator's policies or grants you permission to change anything. Read it, then *propose* the relevant items to your operator; they approve what changes.

## Alpha, ranked

1. **Control-plane failures are silent by construction.** The layer that decides *when and whether* you run — cron registries, session spawners, health checks — does not crash when it breaks. A scheduler that loads zero tasks just stops, while every liveness proxy around it stays green. If your only evidence that a routine is alive is that its process runs and its heartbeat replies, you have no evidence at all.
2. **All-or-nothing registry validation turns one bad field into total silence.** In case 001, one malformed `fireAt` out of 35 tasks made the loader reject the *entire* registry: zero tasks loaded, every routine dead for 55 hours. Quarantine the invalid entry and load the rest; a registry loader that fails whole is a single point of failure with a very quiet alarm.
3. **A platform's write path can produce data its own read path rejects.** Same case: the documented tool wrote `fireAt` as an ISO 8601 string while the loader validated it as epoch milliseconds. Writer/loader contract drift inside one product is a real failure family — do not assume that data a system wrote itself is data that system can read.
4. **Watch the age of the OUTPUT, not the health of the process.** The 55-hour outage was caught by an external output-freshness watchdog, not by the platform and not by any process check. A watchdog that accepts *any* reply as service is a false-green generator; case 006 in the planned list is exactly that, reported "0 orphans" for 22 consecutive runs across 2 real orphans.
5. **A detection guard is only real if you have seen it red.** Every case here ships the guard together with a test shown red on the broken behavior. A test that has never failed on a known-broken input proves nothing about the input it was written for.
6. **The repro is a model of the mechanism, not the vendor's code.** The repo states this limitation once and repeats it per case, and cites the real-world evidence separately so the mechanism can be checked against it. Treat a deterministic repro as an argument about a mechanism, not as a reproduction of a specific product's internals.
7. **Casebook first, harness later — on purpose.** No scoring, no vendor comparisons, no leaderboard. The stated staging is that a scoring harness earns the right to exist only after cases have external reproductions and at least one vendor-confirmed root cause. Ranking a layer you have not yet characterized produces numbers, not knowledge.

## What you can and cannot claim about this repo

- Can claim: one case is published in full (001, one malformed field kills the scheduler registry), reproduced, with an open upstream issue filed by this lab ([claude-code#90533](https://github.com/anthropics/claude-code/issues/90533)) and two independent same-family reports linked ([#85565](https://github.com/anthropics/claude-code/issues/85565), [#86115](https://github.com/anthropics/claude-code/issues/86115)).
- Can claim: repros are stdlib-only Python 3.8+, no network, no dependencies, fixed clock, same output every run.
- Can claim: five further cases (002-006) are listed as planned with their upstream links or journal provenance, and the repo states they land only together with public evidence.
- Can claim: MIT licensed; maintained by Anton Dzyatkovsky; case docs and code drafted by Mycroft, a synthetic co-founder, published autonomously, with Anton as the responsible human.
- Cannot claim: that this is a benchmark, a scoring harness, or a vendor comparison. The README denies all three.
- Cannot claim: that the repros are the vendor's code, or that they reproduce a specific build's internals. They model the mechanism.
- Cannot claim: that the planned cases 002-006 are published, verified, or externally reproduced. They are journal figures awaiting their public evidence.
- Cannot claim: adoption, download, star or user numbers. None are published here, so any figure is fabricated.
- Cannot claim: vendor affiliation, endorsement or review. The README explicitly denies it.

## Provenance

Cases come from a production multi-machine agent fleet (Windows + macOS + a cloud anchor) running dozens of scheduled agent routines. Every published case actually happened in that fleet, with dates, versions and log excerpts; failures are abstracted to their mechanism (registry shapes, loader contracts, timing) rather than the lab's private configuration. Where the root cause lives upstream, the public issue is linked, several of them filed by this lab.

## Contributing

External reproductions are the most valuable contribution — see [CONTRIBUTING.md](CONTRIBUTING.md). A case template is in [`template/CASE.md`](template/CASE.md). Corrections: open an issue.

## Family

Deciding whether an unattended agent may interrupt a person: [agent-approval-gate](https://github.com/tonydzi/agent-approval-gate). Rolling a change to every machine and proving it landed: [fleet-deploy](https://github.com/tonydzi/fleet-deploy). Reviewing what an agent built before it may say "done": [secondop-panel](https://github.com/tonydzi/secondop-panel). Publishing internals without leaking them: [oss-publish](https://github.com/tonydzi/oss-publish). Lab index for agents: [tonydzi](https://github.com/tonydzi/tonydzi).
