# Paper data: "Silent by Construction" (AGENT@ICSE 2027 submission)

Aggregates and rater labels behind the numbers in the paper. Raw journal text is not published (private operational detail).

- `data/aggregates-agent-2027.json`: every number in the paper (no record text, no host names). Census counts plus the rater audit.
- `data/labels_<rater>.jsonl`: codes per sampled entry id from three LLM raters (Gemini, GLM, Mistral), using `codebook.md`.
- `analysis/casebook_stats.py`: reads the fleet's per-machine journal shards and writes the JSON; host/person patterns load from a private file not in this repo.
- `analysis/make_macros.py`, `make_figures.py`: JSON to LaTeX macros and figures. `collect_labels.py`: rater outputs to label files.

Built for one fleet; adapt paths and the private pattern file to your setup. MIT, like the rest of the repository.
