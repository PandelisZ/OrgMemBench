"""The basic (neutral) answerer — for systems that don't ship their own.

mem0, mem0-platform, zep-cloud, and graphiti are retrieval-only: they return
memories/facts, not a prose answer. The runner wraps their ``retrieved_context``
with THIS neutral, system-agnostic answerer so every system is judged on a prose
answer rather than a pile of snippets.

Two hard rules this file exists to enforce:
1. It is deliberately SIMPLE and tuned to NO system, so no contestant gets an
   unfair, system-specific answerer.
2. Same model as every other LLM role (Sonnet 4.6 + extended thinking) — only
   the prompt differs across answerer roles.

Systems that produce their own answer (e.g. gbrain `think`) set
``self_answers = True`` and never reach this module.
"""

from __future__ import annotations

from .llm import AnthropicLLM, LLMResponse

# Neutral, org-domain answerer. No system-specific tuning.
BASIC_ANSWER_PROMPT = """You are answering a question about an organization, using only the retrieved records below. The records are drawn from the company's own history across channels — Slack messages, emails, meeting notes and transcripts, documents, and tickets — and may span several years.

Instructions:
- Read ALL of the retrieved records before answering; relevant details are often scattered across several of them.
- Answer the question directly and specifically, using ONLY information present in the records. Prefer specific names, dates, decisions, and numbers over vague descriptions.
- When several records describe the same topic at different dates, use the dates to determine the correct answer (for example the most recent decision, or the one in effect on the date the question asks about).
- For "how many" or list questions, enumerate every distinct item you find, then give the answer.
- Do NOT invent names, dates, or facts that do not appear in the records. If the records genuinely do not contain the answer, say so and report what the records do show.

Retrieved records:
{context}

Question: {question}

Give a direct, specific answer."""

# Cap context fed to the answerer (chars). Sonnet 4.6 has plenty of room; this
# bounds cost for pathological top-k blowups.
_MAX_CONTEXT_CHARS = 40_000


def basic_answer(question: str, retrieved_context: str, llm: AnthropicLLM) -> LLMResponse:
    """Run the neutral basic answerer over retrieved context.

    Caller must ensure we're not in dry-run (AnthropicLLM.complete hard-guards
    anyway). Returns the full LLMResponse so the runner can record cost.
    """
    context = (retrieved_context or "").strip() or "(no records retrieved)"
    prompt = BASIC_ANSWER_PROMPT.format(context=context[:_MAX_CONTEXT_CHARS], question=question)
    return llm.complete(prompt)
