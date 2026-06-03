# Security Policy

OrgMemBench is a research benchmark: a synthetic corpus, an evaluation harness, and adapters that
call third-party memory systems.

## Reporting a vulnerability

If you find a security issue in the harness, an adapter, or the Docker setup, please report it
**privately** rather than opening a public issue:

- Open a [private security advisory](../../security/advisories/new) on this repository, or
- Contact the maintainer via [GitHub](https://github.com/JackCGardner).

We will acknowledge your report and keep you updated on a fix.

Please **do not include real credentials** in any report. The harness reads API keys from your
environment / `.env` (which is gitignored) and never logs them.

## Scope

- **In scope:** the evaluation harness (`orgmembench/`), the adapters, the generation pipeline
  (`generation/`), and the Docker setup.
- **Out of scope:** vulnerabilities in the third-party memory systems themselves (report those
  upstream) and in vendored upstream code under `vendor/`.
