"""helix-corpus CLI.

Single entry point for running pipeline stages. Reads the LLM-endpoint
configuration from env vars (the ``GRAPHIFY_LLM_*`` contract).

Examples::

    helix-corpus smoke                      # sanity-check the LLM endpoint
    helix-corpus run --stage A --size small # canon generation
    helix-corpus run --stage B --size small
    helix-corpus run --stage all --size small

In Phase 1 only ``smoke`` is functional; the stage runners are stubs
that raise NotImplementedError until their phase lands. The CLI is
scaffolded now so each subsequent phase plugs into a fixed surface.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import logging
import os
import sys
from pathlib import Path


STAGES = ("A", "B", "B6", "C", "C2", "C3", "C4", "C5", "D", "E", "G", "F")
# Ordered stage list. C2 (atmosphere) + C3 (customer depth) + C4
# (long-form: transcripts/docs) + C5 (fragment dispersal) run after C
# (event-bound corpus) and before D (noise injection over the corpus).
_STAGE_MODULES = {
    "A": "helix_corpus.pipeline.stage_a_canon",
    "B": "helix_corpus.pipeline.stage_b_graph",
    "B6": "helix_corpus.pipeline.stage_b6_supersession",
    "C": "helix_corpus.pipeline.stage_c_corpus",
    "C2": "helix_corpus.pipeline.stage_c2_atmosphere",
    "C3": "helix_corpus.pipeline.stage_c3_customer_depth",
    "C4": "helix_corpus.pipeline.stage_c4_longform",
    "C5": "helix_corpus.pipeline.stage_c5_dispersal",
    "D": "helix_corpus.pipeline.stage_d_noise",
    "E": "helix_corpus.pipeline.stage_e_questions",
    "G": "helix_corpus.pipeline.stage_g_emergent",
    "F": "helix_corpus.pipeline.stage_f_validate",
}
# 'all' runs these in order. C4 appends evidence slots to events, so E
# (which reads evidence_in_corpus) runs after it.
_STAGE_ORDER = ["A", "B", "B6", "C", "C2", "C3", "C4", "C5", "D", "E", "G", "F"]


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


async def _cmd_smoke(args: argparse.Namespace) -> int:
    from helix_corpus.llm import HelixLLM

    llm = HelixLLM()
    print(f"[smoke] base_url={llm.client.base_url}")
    print(f"[smoke] model={llm.client.default_model}")
    # Use a generous max_tokens because gpt-oss spends most of its budget
    # on the (hidden) reasoning channel; if max_tokens is too small the
    # final content can be empty even though the model "knew" the answer.
    # reasoning_effort=low keeps the smoke test snappy for a trivial echo.
    out = await llm.call_text(
        system="You are a terse echo.",
        user="Reply with exactly the word PONG and nothing else.",
        reasoning_effort="low",
        max_tokens=512,
    )
    print(f"[smoke] reply={out!r}")
    await llm.aclose()
    return 0 if "pong" in out.lower() else 1


async def _cmd_run(args: argparse.Namespace) -> int:
    if args.stage == "all":
        stages = list(_STAGE_ORDER)
    elif args.stage in STAGES:
        stages = [args.stage]
    else:
        print(f"unknown stage: {args.stage}", file=sys.stderr)
        return 2

    data_dir = Path(args.data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    # Stage G (emergent-pattern questions + their evidence) is LARGE-TIER-ONLY.
    # Emergent patterns need a deep behavioural corpus to be reconstructable and
    # are not comparable across the small/medium tiers, so we only generate them
    # at large+ (see datasets/README.md). 'all' and an explicit '--stage G' both
    # skip emergent generation for small/medium.
    _EMERGENT_TIERS = ("large", "xl", "xxl")
    for stage in stages:
        if stage == "G" and args.size not in _EMERGENT_TIERS:
            print(
                f"[run] Stage G (emergent) is large-tier-only; "
                f"skipping for size={args.size}."
            )
            continue
        module_name = _STAGE_MODULES[stage]
        mod = importlib.import_module(module_name)
        print(f"[run] Stage {stage} — {module_name}")
        try:
            await mod.run(size=args.size, data_dir=str(data_dir))
        except NotImplementedError as exc:
            print(f"[run] Stage {stage} NOT IMPLEMENTED: {exc}", file=sys.stderr)
            return 3
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="helix-corpus",
        description="Helix benchmark corpus generation (Stages A-F).",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("smoke", help="Smoke-test the orchestrator endpoint.")

    p_run = sub.add_parser("run", help="Run one or more pipeline stages.")
    p_run.add_argument(
        "--stage",
        required=True,
        choices=["A", "B", "B6", "C", "C2", "C3", "C4", "C5", "D", "E", "G", "F", "all"],
        help="Which stage to run. 'all' runs A,B,C,C2,C3,C4,C5,D,E,F in order.",
    )
    p_run.add_argument(
        "--size",
        default=os.getenv("HELIX_SIZE", "small"),
        choices=["small", "medium", "large"],
        help="Generation scope. Default: env HELIX_SIZE or 'small'.",
    )
    p_run.add_argument(
        "--data-dir",
        default=os.getenv("HELIX_DATA_DIR", "./data"),
        help="Where artefacts get written. Default: env HELIX_DATA_DIR or './data'.",
    )

    p_repair = sub.add_parser(
        "repair",
        help="Repair corpus artefacts that failed Stage F substrate check "
             "(missing ground-truth facts). Regenerates with explicit "
             "must-contain directive; deterministic append fallback.",
    )
    p_repair.add_argument(
        "--size",
        default=os.getenv("HELIX_SIZE", "small"),
        choices=["small", "medium", "large"],
    )
    p_repair.add_argument(
        "--data-dir",
        default=os.getenv("HELIX_DATA_DIR", "./data"),
    )

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)

    if args.cmd == "smoke":
        return asyncio.run(_cmd_smoke(args))
    if args.cmd == "run":
        return asyncio.run(_cmd_run(args))
    if args.cmd == "repair":
        from helix_corpus.pipeline import repair_substrate
        data_dir = Path(args.data_dir).resolve()
        return asyncio.run(repair_substrate.run(size=args.size, data_dir=str(data_dir))) or 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
