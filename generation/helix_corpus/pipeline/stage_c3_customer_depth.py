"""Stage C3 — Customer-touchpoint depth.

Depth, not breadth: keep ~30 customers but build a multi-year stream of
touchpoints around each — QBR notes, support tickets, escalations,
renewal/expansion discussions, contract redlines. This is "the depth of
information about customers and how it evolved over time" — the texture
a memory system must trace to reconstruct an account's true state.

Walks each customer's lifetime (first_year → last_year/now), generating
a batch of touchpoints per active quarter. Batched (one LLM call per
customer-quarter produces ~3-4 records).

Customer-side personas are synthesised on the fly from the customer's
record (champion / buyer names) so the corpus has named external voices.

Outputs: artefacts under ``corpus/_customers/<customer_id>/`` and index
rows appended to ``corpus_index.jsonl`` with role="secondary",
genre="customer_call_notes".
"""

from __future__ import annotations

import json
import logging
import random
import re
from pathlib import Path
from typing import Any

from helix_corpus.checkpoint import Checkpoint
from helix_corpus.llm import HelixLLM

logger = logging.getLogger("helix_corpus.stage_c3")

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "stage_c3"
CURRENT_YEAR = 2026
COMPANY_NAME = "Helix Logistics"
COMPANY_ARCHETYPE = (
    "B2B SaaS for mid-market freight-forwarding companies, "
    "founded in 2020, ~85 employees by 2025"
)
COMPANY_ONE_LINER = f"{COMPANY_NAME}: {COMPANY_ARCHETYPE}."

# Per-size: how many customer-quarters to generate touchpoints for, and
# batch size. Large covers most customer-quarters across the lifetime.
SIZE_PARAMS: dict[str, dict[str, int]] = {
    "small":  {"max_customer_quarters": 6,    "touchpoints_per_batch": 3},
    "medium": {"max_customer_quarters": 40,   "touchpoints_per_batch": 3},
    # Large: deep multi-year texture per account. Trimmed 1000->400
    # (lower-value tail) since the run was projecting ~6M tokens, over
    # the ~5M target; still gives every customer multiple touchpoints.
    "large":  {"max_customer_quarters": 400, "touchpoints_per_batch": 5},
}


def _load_template(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def _load_inputs(data_dir: Path) -> dict[str, Any]:
    canon = data_dir / "helix_canon"
    skeleton = json.loads((canon / "skeleton.json").read_text(encoding="utf-8"))
    personas = [
        json.loads(l) for l in (canon / "personas.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    customers = []
    for fn in ("customers.jsonl", "historical_customers.jsonl"):
        p = canon / fn
        if p.exists():
            customers.extend(
                json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()
            )
    return {"skeleton": skeleton, "personas": personas, "customers": customers}


def _era_for(year: int, eras: list[dict]) -> dict:
    for e in eras:
        try:
            if int(e["start"][:4]) <= year <= int(e["end"][:4]):
                return e
        except (KeyError, ValueError, IndexError):
            continue
    return eras[0] if eras else {"name": "?"}


def _cs_and_sales_personas(personas: list[dict], year: int) -> list[dict]:
    """Helix-side people who'd work an account: CS, Sales, sometimes
    Support/Eng. Filter to active in the year, prefer CS/Sales roles."""
    out = []
    for p in personas:
        try:
            if int(p.get("joined_year", 9999)) > year:
                continue
        except (TypeError, ValueError):
            continue
        left = p.get("left_year")
        if left is not None:
            try:
                if int(left) < year:
                    continue
            except (TypeError, ValueError):
                pass
        role = (p.get("role_history") or [{}])[0].get("role", "").lower()
        score = 2 if any(k in role for k in ("custom", "success", "sales", "account", "support")) else 1
        out.append((score, p))
    out.sort(key=lambda x: -x[0])
    return [p for _, p in out[:10]]


def _customer_side_names(customer: dict) -> list[str]:
    """Derive customer-side rep names from the customer record, or invent
    stable ones from the customer name."""
    names = []
    # narrative_roles / contract_notes sometimes name people; otherwise
    # synthesise deterministic placeholder names per customer.
    base = re.sub(r"[^A-Za-z]", "", customer.get("name", "Acme"))[:6] or "Acme"
    seed = sum(ord(c) for c in base)
    rng = random.Random(seed)
    first = ["Jordan", "Priya", "Sam", "Lena", "Marco", "Aisha", "Tom", "Nadia", "Diego", "Mei"]
    last = ["Reyes", "Okafor", "Bauer", "Costa", "Singh", "Walsh", "Romano", "Haddad", "Park", "Nystrom"]
    for _ in range(2):
        names.append(f"{rng.choice(first)} {rng.choice(last)}")
    return names


async def run(*, size: str, data_dir: str) -> None:
    if size not in SIZE_PARAMS:
        raise ValueError(f"unknown size {size}")
    params = SIZE_PARAMS[size]
    data_root = Path(data_dir)
    inputs = _load_inputs(data_root)

    if not inputs["customers"]:
        logger.warning("Stage C3: no customers — skipping.")
        return

    cust_root = data_root / "corpus" / "_customers"
    cust_root.mkdir(parents=True, exist_ok=True)
    index_file = data_root / "corpus_index.jsonl"
    cp = Checkpoint(data_root / ".checkpoints" / "stage_c3.jsonl")

    # Build (customer, year, quarter) candidates across each customer's
    # lifetime, then cap at max_customer_quarters.
    candidates: list[tuple[dict, int, int]] = []
    for c in inputs["customers"]:
        try:
            first = int(c.get("first_year", 2021))
        except (TypeError, ValueError):
            first = 2021
        last = c.get("last_year")
        try:
            last = int(last) if last is not None else CURRENT_YEAR
        except (TypeError, ValueError):
            last = CURRENT_YEAR
        for y in range(first, last + 1):
            for q in range(1, 5):
                candidates.append((c, y, q))

    rng = random.Random(42)
    rng.shuffle(candidates)
    candidates = candidates[: params["max_customer_quarters"]]
    logger.info("Stage C3: %d customer-quarters to generate", len(candidates))

    llm = HelixLLM()
    written = 0
    try:
        for c, y, q in candidates:
            cid = c.get("customer_id", "C-XXXX")
            slot_id = f"CUST-{cid}-{y}Q{q}"
            if cp.is_done(slot_id):
                continue
            era = _era_for(y, inputs["skeleton"].get("eras", []))
            helix_people = _cs_and_sales_personas(inputs["personas"], y)
            helix_block = "\n".join(
                f"- {p.get('display_name','?')} ({(p.get('role_history') or [{}])[0].get('role','?')})"
                for p in helix_people
            ) or "(account team)"
            cust_block = "\n".join(f"- {n}" for n in _customer_side_names(c))

            prompt = _load_template("customer_touchpoints.md").format(
                company_one_liner=COMPANY_ONE_LINER,
                customer_name=c.get("name", "?"),
                customer_industry=c.get("industry", "logistics"),
                customer_arc=str(c.get("arc_summary", ""))[:300],
                customer_status=c.get("outcome", "active"),
                year=y, quarter=q,
                era_name=era.get("name", "?"),
                helix_personas_block=helix_block,
                customer_personas_block=cust_block,
                n_touchpoints=params["touchpoints_per_batch"],
            )
            text = await llm.call_text(stage="C", user=prompt, reasoning_effort="low", max_tokens=4000)
            if not text.strip():
                cp.mark_done(slot_id, status="empty")
                continue
            cdir = cust_root / cid
            cdir.mkdir(parents=True, exist_ok=True)
            out_path = cdir / f"{slot_id}.md"
            out_path.write_text(
                f"<!-- customer_depth customer={cid} {y}-Q{q} role=secondary -->\n\n" + text,
                encoding="utf-8",
            )
            with index_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "slot_id": slot_id, "event_id": None, "role": "secondary",
                    "genre": "customer_call_notes", "author": None,
                    "customer_id": cid,
                    "path": str(out_path.relative_to(data_root)), "chars": len(text),
                }, default=str) + "\n")
            cp.mark_done(slot_id, status="ok", chars=len(text))
            written += 1
            if written % 25 == 0:
                logger.info("Stage C3: %d customer touchpoints written", written)

        logger.info("Stage C3 complete. %d customer-quarter batches written.", written)
    finally:
        await llm.aclose()
