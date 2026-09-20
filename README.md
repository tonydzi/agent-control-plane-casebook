# Agent Control Plane Casebook

Reproducible failure cases from the **control plane** of a real, production multi-agent
fleet — the schedulers, registries, dispatchers and watchdogs that decide *when and whether* agents run, each case carrying a runnable repro such as [incidents/001-one-bad-entry-kills-the-scheduler/repro.py](incidents/001-one-bad-entry-kills-the-scheduler/repro.py). Not the models. The plumbing that launches them.

**Independent.** This project is not affiliated with, endorsed by, or reviewed by
Anthropic, OpenAI, Hugging Face, or any other vendor. Upstream links point at public
bug trackers, several to reports we filed ourselves.

## Run one in ten seconds

No install, no dependencies, no network. Python 3.8+ and its standard library:

```bash
git clone https://github.com/tonydzi/agent-control-plane-casebook
python agent-control-plane-casebook/incidents/001-one-bad-entry-kills-the-scheduler/repro.py
```

```
mode=all-or-nothing  on_disk=6 loaded=0 fired=0 dropped=6 alarm=none (SILENT)
mode=quarantine      on_disk=6 loaded=5 fired=5 quarantined=1 alarm=PARITY on_disk=6 loaded=5
mode=healthy         on_disk=6 loaded=6 fired=6 quarantined=0 alarm=none
repro: OK - mechanism demonstrated
```

Six tasks on disk, zero loaded, zero fired, and not one alarm anywhere. That first line is
what a dead scheduler looks like from the outside, which is why nobody notices it for days.

**Did it reproduce on your stack, or did it not?** Both answers are worth an issue: name the
case, your OS and runtime version, and what you actually saw. Outside reproductions are what
move a case from "happened to us" to "happens", and they are the contribution this book needs
most.

## Why this exists

Model quality gets benchmarked constantly. The layer that actually runs agents in
production — cron registries, session spawners, health checks — mostly gets debugged
in private and forgotten. Its failures share one trait: **they are silent by
construction**. A scheduler that loads zero tasks doesn't crash; it just stops, while every liveness proxy around it stays green — that is case 001, written up in [incidents/001-one-bad-entry-kills-the-scheduler/README.md](incidents/001-one-bad-entry-kills-the-scheduler/README.md).

We run a multi-machine agent fleet (Windows + macOS + a cloud anchor) with dozens of
scheduled agent routines. Every case in this book actually happened to us, in production, with dates, versions and log excerpts in the shape [template/CASE.md](template/CASE.md) prescribes — and where the root cause lives upstream, a public issue is linked.

## What a case is

Each case ships as a directory under [`incidents/`](incidents/) with:

- **Symptom** — what the operator saw (usually: nothing).
- **Root cause** — the mechanism, stated plainly.
- **Deterministic repro** such as [incidents/001-one-bad-entry-kills-the-scheduler/repro.py](incidents/001-one-bad-entry-kills-the-scheduler/repro.py) — a stdlib-only Python model of the mechanism (Python 3.8+,
  no network, no dependencies, fixed clock, same output every run; use `python3` where
  `python` isn't aliased).
- **Detection guard** such as [incidents/001-one-bad-entry-kills-the-scheduler/test_registry_guard.py](incidents/001-one-bad-entry-kills-the-scheduler/test_registry_guard.py) — the check that turns the silent failure into an alarm, with a
  test that is shown red on the broken behavior.
- **Fix / mitigation and residual risk** — what actually resolved it, and what still can bite, in the section [template/CASE.md](template/CASE.md) reserves for it.
- **Evidence** — versions, dates, upstream links.

An honest limitation, stated once and repeated per case: repro scripts like [incidents/002-restart-refires-ran-and-disabled-tasks/repro.py](incidents/002-restart-refires-ran-and-disabled-tasks/repro.py) model the
*mechanism* deterministically; they are not the vendor's code. The real-world evidence
is cited separately so you can check the mechanism against it.

## Cases

| # | Title | Status | Upstream |
|---|-------|--------|----------|
| [001](incidents/001-one-bad-entry-kills-the-scheduler/) | One malformed field silently kills the whole scheduler registry | reproduced · upstream open | [claude-code#90533](https://github.com/anthropics/claude-code/issues/90533) |
| [002](incidents/002-restart-refires-ran-and-disabled-tasks/) | A restart re-fires already-run and disabled tasks, invisibly | reproduced · upstream open | [claude-code#74055](https://github.com/anthropics/claude-code/issues/74055) |
| [007](incidents/007-a-second-list-makes-the-reader-report-zero/) | A registry that grew a second top-level list makes readers report a confident zero | reproduced · upstream open | [claude-code#82056](https://github.com/anthropics/claude-code/issues/82056) |

Planned — each already documented in our incident journal; a case only lands here
together with its public evidence (log excerpt or upstream link), the counters below
are journal figures that will be published with the case:

- **003 — Split-brain registries:** per-account × per-workspace task stores make
  routines invisible after an account switch (measured: 269 task prompts on disk, 23
  registered) — [claude-code#89840](https://github.com/anthropics/claude-code/issues/89840)
- **004 — Encoding kills the cron:** a BOM-less `.ps1` written by an agent parses as
  ANSI and dies only when scheduled, with no log —
  [claude-code#90962](https://github.com/anthropics/claude-code/issues/90962)
- **005 — Clone storm:** a remote dispatcher duplicates one prompt into N parallel
  sessions (fleet journal, 6 recurrences)
- **006 — Watchdog false-green:** a health check that accepts *any* reply as service
  reported "0 orphans" for 22 consecutive runs across 2 real orphans (fleet journal)

Case numbers are permanent once assigned, including to a planned case, so a case that ships before its lower-numbered neighbours takes the next free number rather than renumbering the queue; the rule lives in [CONTRIBUTING.md](CONTRIBUTING.md).

## Methodology and scope (v0)

- **Our own stack only.** No scoring, no vendor comparisons, no leaderboard — the scope is fixed in [CONTRIBUTING.md](CONTRIBUTING.md). This is a
  casebook, not a benchmark — deliberately. A scoring harness only earns the right to exist after cases have external reproductions and at least one vendor-confirmed root cause, which is the bar [CONTRIBUTING.md](CONTRIBUTING.md) sets. That is the staged plan, in that order.
- Failures are abstracted to their mechanism (registry shapes, loader contracts,
  timing), not our private configuration.
- External reproductions are the most valuable contribution — see
  [CONTRIBUTING.md](CONTRIBUTING.md).

## Authorship

Maintained by [Anton Dzyatkovsky](https://github.com/tonydzi). Case docs and code are
drafted by Mycroft — Anton's synthetic co-founder, an AI agent — and published
autonomously; Anton is the responsible human for this repository. Every commit carries `Assisted-by` provenance trailers; the repository is licensed [MIT](LICENSE) and citable via [CITATION.cff](CITATION.cff). Corrections: open an issue.

License: [MIT](LICENSE).

---

<!--ecosystem-map:start-->

## 🧩 One piece of a working system

This repository is one piece lifted out of a live operation: one non-technical founder, an AI
cofounder, and a fleet of machines that reach consensus with each other and wake the human only
for money or the irreversible. It was extracted after it survived production, not written as a
demo — and it runs on its own: nothing here phones home to the rest.

**See how the whole thing fits together → [SYSTEM.md](https://github.com/tonydzi/tonydzi/blob/main/SYSTEM.md)**

Its closest neighbours in the **gates** layer: [`break-it-first`](https://github.com/tonydzi/break-it-first) · [`verbatim-citation-gate`](https://github.com/tonydzi/verbatim-citation-gate) · [`verdict-contract`](https://github.com/tonydzi/verdict-contract)

<!--ecosystem-map:end-->

## AI contributors

This project is built by a human + AI team, and the git log says so: Claude writes most of
the code, Codex and Grok review it, Gemini feeds the research. Each is credited on a commit
**only if its output changed that commit's content** — no decorative credits. Lab-wide
policy, one source for every repo: [AI-CONTRIBUTORS.md](https://github.com/tonydzi/.github/blob/main/AI-CONTRIBUTORS.md).

<!-- READ-WITH-AI:START (generated by read_with_ai.py - do not hand-edit) -->

### READ THIS WITH AI

One click and an agent reads the repo, pulls out the patterns and helps you apply them to your own work.

<a href="https://chatgpt.com/codex?prompt=Read%20this%20repo%3A%20https%3A%2F%2Fgithub.com%2Ftonydzi%2Fagent-control-plane-casebook%20%28%E2%80%9Cagent-control-plane-casebook%E2%80%9D%20-%20Reproducible%20control-plane%20failures%20from%20a%20production%20multi-agent%20fleet%3A%20schedulers%2C%20registries%2C%20watchdogs.%20Independent%20casebook%2C%20not%20a%20benchmark%20%28yet%29%29.%20Work%20out%20what%20problem%20it%20actually%20solves%2C%20pull%20out%20the%20reusable%20patterns%20and%20help%20me%20apply%20them%20to%20my%20own%20setup.%20Start%20by%20asking%20what%20I%20am%20working%20on."><img alt="Codex - open" src="https://img.shields.io/badge/Codex-open-000000?style=for-the-badge&logo=openai&logoColor=white"></a> <a href="https://chatgpt.com/?q=Read%20this%20repo%3A%20https%3A%2F%2Fgithub.com%2Ftonydzi%2Fagent-control-plane-casebook%20%28%E2%80%9Cagent-control-plane-casebook%E2%80%9D%20-%20Reproducible%20control-plane%20failures%20from%20a%20production%20multi-agent%20fleet%3A%20schedulers%2C%20registries%2C%20watchdogs.%20Independent%20casebook%2C%20not%20a%20benchmark%20%28yet%29%29.%20Work%20out%20what%20problem%20it%20actually%20solves%2C%20pull%20out%20the%20reusable%20patterns%20and%20help%20me%20apply%20them%20to%20my%20own%20setup.%20Start%20by%20asking%20what%20I%20am%20working%20on."><img alt="ChatGPT - open" src="https://img.shields.io/badge/ChatGPT-open-10a37f?style=for-the-badge&logo=openai&logoColor=white"></a> <a href="https://claude.ai/new?q=Read%20this%20repo%3A%20https%3A%2F%2Fgithub.com%2Ftonydzi%2Fagent-control-plane-casebook%20%28%E2%80%9Cagent-control-plane-casebook%E2%80%9D%20-%20Reproducible%20control-plane%20failures%20from%20a%20production%20multi-agent%20fleet%3A%20schedulers%2C%20registries%2C%20watchdogs.%20Independent%20casebook%2C%20not%20a%20benchmark%20%28yet%29%29.%20Work%20out%20what%20problem%20it%20actually%20solves%2C%20pull%20out%20the%20reusable%20patterns%20and%20help%20me%20apply%20them%20to%20my%20own%20setup.%20Start%20by%20asking%20what%20I%20am%20working%20on."><img alt="Claude - open" src="https://img.shields.io/badge/Claude-open-d97757?style=for-the-badge&logo=anthropic&logoColor=white"></a>

<details>
<summary>Copy the prompt (works in any agent: Gemini, Grok, a local model, your own CLI)</summary>

```text
Read this repo: https://github.com/tonydzi/agent-control-plane-casebook (“agent-control-plane-casebook” - Reproducible control-plane failures from a production multi-agent fleet: schedulers, registries, watchdogs. Independent casebook, not a benchmark (yet)). Work out what problem it actually solves, pull out the reusable patterns and help me apply them to my own setup. Start by asking what I am working on.
```

</details>

<sub>— TonyDzi, Palo Alto AI Research Lab · second brain, agent coordination, persistent memory: github.com/tonydzi</sub>

<!-- READ-WITH-AI:END -->
