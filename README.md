# Agent Control Plane Casebook

Reproducible failure cases from the **control plane** of a real, production multi-agent
fleet — the schedulers, registries, dispatchers and watchdogs that decide *when and
whether* agents run. Not the models. The plumbing that launches them.

**Independent.** This project is not affiliated with, endorsed by, or reviewed by
Anthropic, OpenAI, Hugging Face, or any other vendor. Upstream links point at public
bug trackers, several to reports we filed ourselves.

## Why this exists

Model quality gets benchmarked constantly. The layer that actually runs agents in
production — cron registries, session spawners, health checks — mostly gets debugged
in private and forgotten. Its failures share one trait: **they are silent by
construction**. A scheduler that loads zero tasks doesn't crash; it just stops, while
every liveness proxy around it stays green.

We run a multi-machine agent fleet (Windows + macOS + a cloud anchor) with dozens of
scheduled agent routines. Every case in this book actually happened to us, in
production, with dates, versions and log excerpts — and where the root cause lives
upstream, a public issue is linked.

## What a case is

Each case ships as a directory under [`incidents/`](incidents/) with:

- **Symptom** — what the operator saw (usually: nothing).
- **Root cause** — the mechanism, stated plainly.
- **Deterministic repro** — a stdlib-only Python model of the mechanism (Python 3.8+,
  no network, no dependencies, fixed clock, same output every run; use `python3` where
  `python` isn't aliased).
- **Detection guard** — the check that turns the silent failure into an alarm, with a
  test that is shown red on the broken behavior.
- **Fix / mitigation and residual risk** — what actually resolved it, and what still can bite.
- **Evidence** — versions, dates, upstream links.

An honest limitation, stated once and repeated per case: the repro scripts model the
*mechanism* deterministically; they are not the vendor's code. The real-world evidence
is cited separately so you can check the mechanism against it.

## Cases

| # | Title | Status | Upstream |
|---|-------|--------|----------|
| [001](incidents/001-one-bad-entry-kills-the-scheduler/) | One malformed field silently kills the whole scheduler registry | reproduced · upstream open | [claude-code#90533](https://github.com/anthropics/claude-code/issues/90533) |

Planned — each already documented in our incident journal; a case only lands here
together with its public evidence (log excerpt or upstream link), the counters below
are journal figures that will be published with the case:

- **002 — Split-brain registries:** per-account × per-workspace task stores make
  routines invisible after an account switch (measured: 269 task prompts on disk, 23
  registered) — [claude-code#89840](https://github.com/anthropics/claude-code/issues/89840)
- **003 — Catch-up storm:** an app restart re-fires tasks that already ran and fires
  `enabled: false` tasks; ghost runs never update `lastRunAt` —
  [claude-code#74055](https://github.com/anthropics/claude-code/issues/74055)
- **004 — Encoding kills the cron:** a BOM-less `.ps1` written by an agent parses as
  ANSI and dies only when scheduled, with no log —
  [claude-code#90962](https://github.com/anthropics/claude-code/issues/90962)
- **005 — Clone storm:** a remote dispatcher duplicates one prompt into N parallel
  sessions (fleet journal, 6 recurrences)
- **006 — Watchdog false-green:** a health check that accepts *any* reply as service
  reported "0 orphans" for 22 consecutive runs across 2 real orphans (fleet journal)

## Methodology and scope (v0)

- **Our own stack only.** No scoring, no vendor comparisons, no leaderboard. This is a
  casebook, not a benchmark — deliberately. A scoring harness only earns the right to
  exist after cases have external reproductions and at least one vendor-confirmed
  root cause. That is the staged plan, in that order.
- Failures are abstracted to their mechanism (registry shapes, loader contracts,
  timing), not our private configuration.
- External reproductions are the most valuable contribution — see
  [CONTRIBUTING.md](CONTRIBUTING.md).

## Authorship

Maintained by [Anton Dzyatkovsky](https://github.com/tonydzi). Case docs and code are
drafted by Mycroft — Anton's synthetic co-founder, an AI agent — and published
autonomously; Anton is the responsible human for this repository. Every commit carries
`Assisted-by` provenance trailers. Corrections: open an issue.

License: [MIT](LICENSE).
