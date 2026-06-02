"""Per-run usage metering — ACTUALS, for comparison against the cost estimate.

After a run, ``build_usage(run)`` rolls up everything the harness can directly
measure (the answerer + judge LLM calls we make ourselves, plus any ingest
tokens the system reports) and the system-native units that map to vendor
dashboards (Mem0 add/retrieval requests, Zep episodes, ...). It also attaches
the pre-run estimate from cost.py so you can eyeball actual vs estimate.

Honest about limits: a self-hosted system's internal extractor (mem0, graphiti)
runs inside its SDK and does NOT surface token usage to us; hosted systems run
ingest/retrieval server-side. Those are listed under ``not_measured`` — read the
provider console for the true total. What we DO measure exactly: the answerer
and the judge (both go through our AnthropicLLM), plus any ingest tokens a
system reports.
"""

from __future__ import annotations

from .schemas import RunResult


def _native_units(system: str, n_artifacts: int, n_queries: int) -> dict:
    """System-native usage counts that line up with each vendor's metering."""
    if system in ("mem0", "mem0-platform"):
        return {"add_requests": n_artifacts, "retrieval_requests": n_queries}
    if system == "zep-cloud":
        return {"episodes": n_artifacts, "retrieval_requests": n_queries}
    if system == "graphiti":
        return {"episodes": n_artifacts}
    if system == "gbrain":
        return {"captures": n_artifacts, "think_calls": n_queries}
    return {}


def _not_measured(system: str) -> list[str]:
    notes = []
    if system in ("mem0", "graphiti"):
        notes.append(f"{system}: ingest/extractor LLM tokens run inside the SDK and "
                     "are not exposed here — see the Anthropic/OpenAI console for the true total.")
    if system in ("mem0-platform", "zep-cloud"):
        notes.append(f"{system}: ingest + retrieval run server-side (hosted) — see the "
                     "vendor dashboard for episodes/requests consumed.")
    if system == "gbrain":
        notes.append("gbrain: `gbrain think` runs in a subprocess; its LLM + ZeroEntropy "
                     "tokens are not surfaced here — see the Anthropic/ZeroEntropy console.")
    return notes


def build_usage(run: RunResult) -> dict:
    """Roll up measured usage + native units + the cost estimate for one run."""
    qs = run.queries
    js = run.judgements
    ans_in = sum(q.input_tokens for q in qs)
    ans_out = sum(q.output_tokens for q in qs)
    ans_cost = sum(q.cost_usd for q in qs)
    ans_calls = sum(1 for q in qs if q.input_tokens or q.output_tokens)
    j_in = sum(j.input_tokens for j in js)
    j_out = sum(j.output_tokens for j in js)
    j_cost = sum(j.cost_usd for j in js)
    measured_cost = round(ans_cost + j_cost, 4)

    # Pre-run estimate for this exact (system, tier).
    est_block: dict = {}
    try:
        from .cost import _cell_cost
        all_in, est = _cell_cost(run.system, run.tier, run.company)
        est_block = {
            "all_in_usd": all_in,
            "ingest_usd": est.get("ingest_usd"),
            "query_usd": est.get("query_usd"),
            "judge_usd": est.get("judge_usd"),
            "embed_usd": est.get("embed_usd"),
            "subscription_usd_month": est.get("subscription_usd_month"),
        }
    except Exception:
        est_block = {"all_in_usd": None}

    return {
        "measured": {
            "answerer": {"calls": ans_calls, "input_tokens": ans_in,
                         "output_tokens": ans_out, "cost_usd": round(ans_cost, 4)},
            "judge": {"calls": len(js), "input_tokens": j_in,
                      "output_tokens": j_out, "cost_usd": round(j_cost, 4)},
            # What WE billed to Anthropic and can prove (answerer + judge). Does
            # NOT include system-internal ingest/retrieval LLM tokens (see below).
            "measured_anthropic_cost_usd": measured_cost,
        },
        "ingest": {
            "n_artifacts": run.ingest.n_artifacts,
            "tokens_stored": run.ingest.tokens_stored,
            "seconds": round(run.ingest.ingest_seconds, 1),
            "llm_input_tokens": run.ingest.llm_input_tokens,
            "llm_output_tokens": run.ingest.llm_output_tokens,
        },
        "native_units": _native_units(run.system, run.ingest.n_artifacts, len(qs)),
        "estimate": est_block,
        "not_measured": _not_measured(run.system),
    }


def usage_report() -> str:
    """Scan results/ and tabulate measured-vs-estimate for every completed run."""
    import json
    from .config import RESULTS_ROOT

    rows = []
    for sysdir in sorted(p for p in RESULTS_ROOT.glob("*") if p.is_dir()):
        for f in sorted(sysdir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            u = (data.get("metrics") or {}).get("usage")
            if not u:
                continue
            rows.append((data.get("system", "?"), data.get("tier", "?"), u))

    if not rows:
        return ("No completed runs with usage yet. Run `orgmembench run --system <s> "
                "--tier <t> --execute`, then re-run `orgmembench usage`.")

    out = ["OrgMemBench USAGE — measured actuals vs pre-run estimate", ""]
    out.append(f"{'system':14} {'tier':7} {'meas $':>8} {'est all-in $':>12} "
               f"{'ans tok(i/o)':>16} {'judge tok(i/o)':>16}  native")
    tot_meas = 0.0
    for system, tier, u in rows:
        m = u["measured"]; e = u["estimate"]
        meas = m["measured_anthropic_cost_usd"]; tot_meas += meas
        a = m["answerer"]; j = m["judge"]
        native = ", ".join(f"{k}={v}" for k, v in (u.get("native_units") or {}).items())
        out.append(
            f"{system:14} {tier:7} {meas:>8.2f} {str(e.get('all_in_usd')):>12} "
            f"{a['input_tokens']:>7}/{a['output_tokens']:<8} "
            f"{j['input_tokens']:>7}/{j['output_tokens']:<8}  {native}")
    out.append("")
    out.append(f"TOTAL measured Anthropic cost (answerer + judge, proven): ${tot_meas:,.2f}")
    out.append("NOTE: measured = the answerer + judge calls we make directly. System-internal")
    out.append("ingest/retrieval LLM + embedding tokens are NOT in this number — read each")
    out.append("provider's console (Anthropic / OpenAI / ZeroEntropy / Mem0 / Zep) for those.")
    return "\n".join(out) + "\n"
