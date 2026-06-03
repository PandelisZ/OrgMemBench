# Contributing to OrgMemBench

Thanks for your interest in improving OrgMemBench. There are three main ways to contribute.

## Add a memory system to the leaderboard

The benchmark is built to be extended, and the leaderboard is open. To evaluate a new system:

1. **Write an adapter** — one file in `orgmembench/adapters/` implementing the small `Adapter`
   interface (ingest, retrieve, and an optional native answerer). See
   [`docs/CONTRIBUTING-AN-ADAPTER.md`](docs/CONTRIBUTING-AN-ADAPTER.md) for the full walkthrough.
2. **Run it** — `orgmembench run --system <name> --tier medium --execute`.
3. **Open a PR** with the adapter and your results. We'll review and add the system to the leaderboard.

Already have predictions? You can score them without writing an adapter:

```bash
orgmembench judge-submission --file preds.jsonl --system <name> --tier medium
```

## Report a data issue

Found a question whose gold answer looks wrong, or a corpus inconsistency? Open a
[data issue](../../issues/new?template=data_issue.yml) with the question id and the artifact(s)
involved. Ground truth is projected deterministically from a source-of-truth graph, so most issues
trace to a specific event or relation we can correct.

## Fix a bug or improve docs

Standard GitHub flow:

1. Fork and create a branch from `main`.
2. Make your change. Keep the harness importable and the free smoke checks green:
   `pip install -e . && orgmembench list && orgmembench stats --tier small`.
3. Open a pull request against `main`; CI runs automatically.

## Development setup

```bash
pip install -e .
orgmembench --help
```

The corpus ships in `datasets/helix/` (small + medium tiers). Per-system reproduction detail is in
[`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md); the methodology is in
[`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By participating, you agree to
uphold it.
