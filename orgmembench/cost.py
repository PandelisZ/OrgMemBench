"""Pre-run cost estimator (standardized + tunable).

Estimates token usage + USD per (system, tier), broken down by which API key
pays. This is an ESTIMATE from a transparent model (the per-system token
profiles below are the assumptions — tune them as you learn each system's real
behavior). After a real run, the harness records ACTUAL ``cost_usd`` per query
+ judge tokens, which is ground truth; this module is for planning.

Run:  orgmembench cost [--tier small] [--all]
"""

from __future__ import annotations

import json

from .config import DATASETS_ROOT

# ---- prices (USD per token) -------------------------------------------------
SONNET_IN = 3.0 / 1_000_000          # Claude Sonnet 4.6 input
SONNET_OUT = 15.0 / 1_000_000        # output (extended-thinking tokens bill as output)
OPENAI_EMBED = 0.02 / 1_000_000      # text-embedding-3-small
ZEROENTROPY = 0.05 / 1_000_000       # gbrain: zembed-1 $0.05/M (+ zerank-2 $0.025/M rerank); pay-as-you-go, Free tier

# ---- judge model (Anthropic, runs for EVERY system, every question) ---------
JUDGE_IN_PER_Q = 2_500               # question + ground truth + rubric + candidate answer
JUDGE_OUT_PER_Q = 4_500              # ~4k extended-thinking + ~0.5k JSON verdict

# ---- shared assumptions -----------------------------------------------------
INGEST_PROMPT_OVERHEAD = 500         # extraction-prompt tokens added per ingest LLM call
QUERY_CTX = 3_000                    # retrieved context tokens fed to a query-side LLM call
QUERY_OUT = 400                      # output tokens per query-side LLM call

# ---- answerer (the prose-answer stage) --------------------------------------
# Every system's retrieval is turned into a prose answer before judging: gbrain
# via `think`, everyone else via the neutral basic
# answerer (orgmembench/answerer.py). That's ONE Sonnet 4.6 + extended-thinking
# call per question, for EVERY system — and it bills YOUR Anthropic key even for
# hosted systems (mem0-platform, zep-cloud), which therefore now pay more than
# just the judge. Thinking tokens bill as output, so the output term is large.
ANSWERER_IN = 4_000                  # retrieved context + the answerer prompt
ANSWERER_OUT = 3_500                 # extended thinking (~budget) + the answer

# ---- hosted subscription tiers (the fee you pay on top of the judge) --------
# Mem0 Platform: (name, $/mo, max_memories, max_retrievals/mo).
MEM0_TIERS = [("free", 0, 10_000, 1_000), ("starter", 19, 50_000, 5_000),
              ("growth", 79, 200_000, 20_000), ("pro", 249, 500_000, 50_000)]
MEM0_MEMORIES_PER_ARTIFACT = 1.5     # mem0 often extracts >1 memory per item (assumption)

# Zep Cloud: EPISODE-metered, per month (verified from the dashboard). One
# graph.add = one episode = one artifact. Retrieval + graph memories are
# UNLIMITED on every tier (so queries cost nothing on Zep). (name, $/mo,
# max_episodes/month). Free resets monthly. Next paid tier is Flex at $125/mo.
ZEP_TIERS = [("free", 0, 1_000), ("flex", 125, 100_000)]

# ---- per-system token profiles (THE tunable assumptions) --------------------
# llm: "anthropic" = its internal LLM bills your ANTHROPIC_API_KEY (we steer it
#      to Sonnet 4.6); "hosted" = runs server-side, billed via the subscription.
# embed: "openai" | "zeroentropy" | "internal"/"hosted" (no metered cost to you).
# query_retrieval_calls = system's own query-time LLM calls (Anthropic-billed,
# SEPARATE from the answerer). 0 for vector/graph retrieval that makes no LLM
# call at query time; hosted systems run retrieval server-side (billed via
# subscription, not Anthropic). gbrain's
# `think` is counted as the answerer, not here. The answerer (1 Sonnet+thinking
# call/question) is added uniformly to EVERY system in estimate_system.
#
# ingest_calls + ingest_out RECALIBRATED 2026-05-25 from measured small-tier
# runs (Anthropic POST counts in run/container logs; output tokens from
# typical per-call sizes). Earlier estimates were 5–10× low for the
# temporal-graph systems (graphiti) — the extractors make many
# calls/artifact (entity + edge + dedup + summarize, sometimes with retries).
# Note: graphiti's calls/artifact grows with graph size (dedup against existing
# entities), so medium/large will be HIGHER than this small-tier rate.
PROFILES: dict[str, dict] = {
    "mem0":          dict(ingest_calls=1.2,  ingest_out=150, query_retrieval_calls=0, llm="anthropic", embed="openai"),       # measured ~149 calls / 121 art
    "mem0-platform": dict(ingest_calls=1.2,  ingest_out=150, query_retrieval_calls=0, llm="hosted",    embed="hosted"),       # server-side; same SDK
    "graphiti":      dict(ingest_calls=17.0, ingest_out=600, query_retrieval_calls=0, llm="anthropic", embed="openai"),       # measured 2008 calls / 121 art = 16.6
    "zep-cloud":     dict(ingest_calls=17.0, ingest_out=600, query_retrieval_calls=0, llm="hosted",    embed="hosted"),       # same engine as graphiti, server-side
    "gbrain":        dict(ingest_calls=0.0,  ingest_out=0,   query_retrieval_calls=0, llm="anthropic", embed="zeroentropy"),  # capture is ZeroEntropy+local, no Anthropic at ingest
    "graphify-oss":  dict(ingest_calls=3.0,  ingest_out=300, query_retrieval_calls=0, llm="anthropic", embed="none"),          # estimate: ~3 LLM calls/artifact (semantic entity+rel extraction); BFS/DFS query = no LLM; no embeddings
}


def _tier_size(tier: str, company: str = "helix") -> tuple[int, int, int]:
    """(n_artifacts, corpus_tokens, n_questions) from index chars + benchmark count."""
    base = DATASETS_ROOT / company / tier
    rows = [json.loads(l) for l in (base / "corpus_index.jsonl").read_text().splitlines() if l.strip()]
    chars = sum(r.get("chars", 0) for r in rows)
    nq = sum(1 for l in (base / "benchmark_v0.0.jsonl").read_text().splitlines() if l.strip())
    return len(rows), chars // 4, nq


def estimate_system(system: str, tier: str, company: str = "helix") -> dict:
    p = PROFILES[system]
    n_art, corpus_tok, n_q = _tier_size(tier, company)
    avg_art = corpus_tok / max(1, n_art)

    ingest_in = n_art * p["ingest_calls"] * (avg_art + INGEST_PROMPT_OVERHEAD)
    ingest_out = n_art * p["ingest_calls"] * p["ingest_out"]
    # System's own query-time retrieval LLM calls (Anthropic for self-hosted;
    # server-side for hosted). SEPARATE from the answerer below.
    retrieval_in = n_q * p["query_retrieval_calls"] * (QUERY_CTX + 200)
    retrieval_out = n_q * p["query_retrieval_calls"] * QUERY_OUT
    judge_in = n_q * JUDGE_IN_PER_Q
    judge_out = n_q * JUDGE_OUT_PER_Q

    # Cost split (all in USD). Judge always bills your Anthropic key.
    judge_usd = judge_in * SONNET_IN + judge_out * SONNET_OUT
    # The answerer (1 Sonnet+thinking call/question) ALWAYS bills your Anthropic
    # key — for every system, hosted included.
    answerer_usd = n_q * (ANSWERER_IN * SONNET_IN + ANSWERER_OUT * SONNET_OUT)
    ingest_usd = retrieval_usd = 0.0
    hosted_note_tokens = 0
    if p["llm"] == "anthropic":
        ingest_usd = ingest_in * SONNET_IN + ingest_out * SONNET_OUT
        retrieval_usd = retrieval_in * SONNET_IN + retrieval_out * SONNET_OUT
    else:  # hosted — ingest/retrieval run server-side, billed via subscription
        hosted_note_tokens = int(ingest_in + ingest_out + retrieval_in + retrieval_out)
    # "query$" column = the system's query-time Anthropic cost: retrieval (if
    # any) + the answerer (always).
    query_usd = retrieval_usd + answerer_usd
    anthropic = judge_usd + ingest_usd + query_usd

    embed_cost = 0.0
    if p["embed"] == "openai":
        embed_cost = corpus_tok * OPENAI_EMBED
    elif p["embed"] == "zeroentropy":
        embed_cost = corpus_tok * ZEROENTROPY

    # Hosted subscription tier needed for THIS tier's ingest volume.
    sub_tier, sub_usd = "-", 0
    if system == "mem0-platform":
        memories = int(n_art * MEM0_MEMORIES_PER_ARTIFACT)
        sub_tier, sub_usd = "custom", -1
        for name, fee, max_mem, max_retr in MEM0_TIERS:
            if memories <= max_mem and n_q <= max_retr:
                sub_tier, sub_usd = name, fee; break
    elif system == "zep-cloud":
        episodes = n_art   # one graph.add per artifact = one episode/month
        sub_tier, sub_usd = "over", -1
        for name, fee, max_ep in ZEP_TIERS:
            if episodes <= max_ep:
                sub_tier, sub_usd = name, fee; break

    return {
        "system": system, "tier": tier, "n_artifacts": n_art,
        "corpus_tokens": corpus_tok, "n_questions": n_q,
        "ingest_usd": round(ingest_usd, 2),
        "query_usd": round(query_usd, 2),
        "judge_usd": round(judge_usd, 2),
        "anthropic_usd": round(anthropic, 2),
        "embed_provider": p["embed"] if p["embed"] in ("openai", "zeroentropy") else "-",
        "embed_usd": round(embed_cost, 3),
        "hosted": p["llm"] == "hosted",
        "hosted_server_tokens": hosted_note_tokens,
        "subscription_tier": sub_tier,
        "subscription_usd_month": sub_usd,
        "total_metered_usd": round(anthropic + embed_cost, 2),
    }


def estimate_tier(tier: str, company: str = "helix") -> list[dict]:
    return [estimate_system(s, tier, company) for s in PROFILES]


# What each system needs to run (keys + a local service), for the prereq summary.
SYSTEM_REQS: dict[str, dict] = {
    "mem0":          dict(keys=["ANTHROPIC_API_KEY", "OPENAI_API_KEY"], service="Qdrant (docker compose up -d qdrant)"),
    "mem0-platform": dict(keys=["ANTHROPIC_API_KEY", "MEM0_API_KEY"], service="none (hosted)"),
    "graphiti":      dict(keys=["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "NEO4J_URI/USER/PASSWORD"], service="Neo4j (docker compose up -d neo4j)"),
    "zep-cloud":     dict(keys=["ANTHROPIC_API_KEY", "ZEP_API_KEY"], service="none (hosted)"),
    "gbrain":        dict(keys=["ANTHROPIC_API_KEY", "ZEROENTROPY_API_KEY"], service="gbrain CLI (bun, pinned) + gbrain init --pglite"),
    "graphify-oss":  dict(keys=["ANTHROPIC_API_KEY"], service="graphifyy CLI (pip install graphifyy==0.8.20 anthropic) — no sidecar needed"),
}


def _cell_cost(system: str, tier: str, company: str = "helix") -> tuple[float, dict]:
    """All-in cost for one (system, tier): token bill + its required hosted sub."""
    e = estimate_system(system, tier, company)
    sub = e["subscription_usd_month"] if (e["hosted"] and e["subscription_usd_month"] > 0) else 0
    return round(e["total_metered_usd"] + sub, 2), e


def plan(budget: float, tiers: list[str] | None = None, company: str = "helix") -> list[dict]:
    """Every (system, tier) with all-in cost, flagged included if < budget."""
    tiers = tiers or ["small", "medium", "large"]
    out = []
    for s in PROFILES:
        for t in tiers:
            cost, e = _cell_cost(s, t, company)
            out.append({"system": s, "tier": t, "cost": cost, "included": cost < budget,
                        "hosted": e["hosted"], "sub_tier": e["subscription_tier"],
                        "sub_usd": e["subscription_usd_month"]})
    return out


def format_plan(budget: float, company: str = "helix") -> str:
    rows = plan(budget, company=company)
    inc = [r for r in rows if r["included"]]
    exc = [r for r in rows if not r["included"]]
    lines = [f"RUN PLAN — every (system, tier) with all-in cost < ${budget:g}", ""]
    lines.append(f"{'system':14} {'small':>9} {'medium':>9} {'large':>9}")
    by = {(r['system'], r['tier']): r for r in rows}
    for s in PROFILES:
        cells = []
        for t in ["small", "medium", "large"]:
            r = by[(s, t)]
            mark = "" if r["included"] else " x"
            cells.append(f"{r['cost']:>7.2f}{mark}")
        lines.append(f"{s:14} {cells[0]:>9} {cells[1]:>9} {cells[2]:>9}")
    lines.append("  ( x = excluded: over budget )")
    lines.append("")
    lines.append(f"INCLUDED: {len(inc)} runs.  EXCLUDED: " +
                 ", ".join(f"{r['system']}-{r['tier']} (${r['cost']:.0f})" for r in exc))
    inc_total = round(sum(r["cost"] for r in inc), 2)
    # subscriptions actually needed (max tier per hosted system among included)
    paid = [r for r in inc if r["hosted"] and r["sub_usd"] > 0]
    lines.append(f"ESTIMATED TOTAL for the plan: ~${inc_total:,.2f}"
                 + ("" if not paid else f" (incl. paid subs: " +
                    ", ".join(f"{r['system']} {r['sub_tier']} ${r['sub_usd']}/mo" for r in paid) + ")"))
    if not paid:
        lines.append("  No paid hosted subscriptions needed — hosted systems stay on their FREE tier in this plan.")
    # prerequisites for the included systems
    inc_systems = sorted({r["system"] for r in inc})
    keys = sorted({k for s in inc_systems for k in SYSTEM_REQS[s]["keys"]})
    lines.append("")
    lines.append("PREREQS for this plan:")
    lines.append("  keys: " + ", ".join(keys))
    for s in inc_systems:
        lines.append(f"  {s:14} service: {SYSTEM_REQS[s]['service']}")
    lines.append("")
    lines.append("COMMANDS (cheapest tier first; runner checkpoints per question):")
    lines.append("  export ORGMEMBENCH_DRY_RUN=0   # plus your keys; bring up services per READY.md")
    for r in sorted(inc, key=lambda x: (["small", "medium", "large"].index(x["tier"]), x["cost"])):
        lines.append(f"  orgmembench run --system {r['system']} --tier {r['tier']} --execute")
    lines.append("  orgmembench leaderboard")
    return "\n".join(lines) + "\n"


def write_run_script(budget: float, path, company: str = "helix") -> None:
    """Phased run script: `./run_plan.sh small|medium|large|all`.

    Small is the end-to-end smoke gate; you recalibrate from actual cost_usd
    before spending on medium/large. Default (no arg) prints usage, runs nothing.
    """
    from pathlib import Path
    rows = [r for r in plan(budget, company=company) if r["included"]]
    by_tier: dict[str, list[dict]] = {"small": [], "medium": [], "large": []}
    for r in sorted(rows, key=lambda x: x["cost"]):
        by_tier[r["tier"]].append(r)

    def phase(tier: str) -> list[str]:
        rs = by_tier[tier]
        sub = round(sum(r["cost"] for r in rs), 2)
        out = [f"run_{tier}() {{", f'  echo ">>> {tier}: {len(rs)} runs, est ~${sub:.2f}"']
        for r in rs:
            out.append(f"  orgmembench run --system {r['system']} --tier {r['tier']} --execute")
        out += ["}", ""]
        return out

    inc_total = round(sum(r["cost"] for r in rows), 2)
    lines = [
        "#!/usr/bin/env bash",
        f"# Auto-generated by `orgmembench plan --budget {budget:g} --write-script`.",
        f"# Every (system, tier) with all-in cost < ${budget:g}. Plan total ~${inc_total:.2f}.",
        "# PREREQS: set API keys + bring up services first (see READY.md).",
        "# Workflow: run `small` first (the smoke gate), read actual cost_usd from",
        "#   results/, recalibrate, THEN run medium / large.",
        "set -uo pipefail",
        "# Load API keys from .env (gitignored) if present — keys never live in git.",
        'ENV_FILE="$(cd "$(dirname "$0")" && pwd)/.env"',
        '[ -f "$ENV_FILE" ] && set -a && . "$ENV_FILE" && set +a',
        'export ORGMEMBENCH_DRY_RUN=0   # real runs (token spend)',
        "",
    ]
    lines += phase("small") + phase("medium") + phase("large")
    lines += [
        'case "${1:-}" in',
        "  small)  run_small ;;",
        "  medium) run_medium ;;",
        "  large)  run_large ;;",
        "  all)    run_small && run_medium && run_large ;;",
        '  *) echo "usage: $0 small|medium|large|all"; exit 1 ;;',
        "esac",
        "orgmembench leaderboard",
        "",
    ]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def format_report(tiers: list[str], company: str = "helix") -> str:
    lines = ["OrgMemBench cost ESTIMATE (model in orgmembench/cost.py; actuals recorded at run time)", ""]
    grand = 0.0
    for tier in tiers:
        rows = estimate_tier(tier, company)
        n_art, corpus_tok, n_q = _tier_size(tier, company)
        lines.append(f"### {tier}: {n_art} artifacts, ~{corpus_tok:,} corpus tokens, {n_q} questions")
        lines.append(f"{'system':14} {'ingest$':>8} {'query$':>7} {'judge$':>7} {'embed$':>7} "
                     f"{'metered$':>9}  {'subscription (hosted)':<24}")
        tier_total = 0.0; sub_total = 0.0
        for r in rows:
            sub = "-"
            if r["hosted"]:
                fee = r["subscription_usd_month"]
                sub = f"{r['subscription_tier']} (${fee}/mo)" if fee >= 0 else f"{r['subscription_tier']} (quote)"
                if fee > 0:
                    sub_total += fee
            lines.append(f"{r['system']:14} {r['ingest_usd']:>8.2f} {r['query_usd']:>7.2f} "
                         f"{r['judge_usd']:>7.2f} {r['embed_usd']:>7.3f} {r['total_metered_usd']:>9.2f}  {sub:<24}")
            tier_total += r["total_metered_usd"]
        lines.append(f"{'TIER METERED TOTAL (all 6, your token bill)':44} ${tier_total:,.2f}")
        lines.append(f"{'+ hosted subscriptions this tier (mem0-platform + zep-cloud)':44} ${sub_total:,.2f}/mo")
        lines.append(f"{'= TIER ALL-IN':44} ${tier_total + sub_total:,.2f}")
        lines.append("")
        grand += tier_total + sub_total
    if len(tiers) > 1:
        lines.append(f"GRAND ALL-IN ({'+'.join(tiers)}, all 6 systems; subs counted once/mo would be lower): ${grand:,.2f}")
        lines.append("NOTE: subscriptions are MONTHLY + cumulative — running several tiers in one")
        lines.append("calendar month needs only the single plan covering the combined volume, not the sum.")
    return "\n".join(lines) + "\n"
