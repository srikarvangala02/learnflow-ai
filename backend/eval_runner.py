import json
import os

import anthropic

_SYSTEM_PROMPT = (
    "You are a student taking a multiple-choice quiz. "
    "Read the context carefully and answer based only on what it contains. "
    "Reply with a single letter: A, B, C, or D. Nothing else."
)

_FOCUS_SYSTEM_PROMPT = (
    "You are an expert educator identifying concepts a student should review. "
    "Your output must be valid JSON and nothing else — no markdown fences, no commentary."
)

_FOCUS_USER_TEMPLATE = """\
A student answered these questions incorrectly:

{wrong_questions}

Source material (narration):
{narration}

Identify up to 3 distinct concepts the student should review. For each, write one sentence \
explaining what to revisit and why it matters, grounded in the source material above.

Return a JSON array with this exact schema:
[
  {{
    "topic": "<the concept label from the question>",
    "explanation": "<one sentence — what to review and why>"
  }}
]

Rules:
- Include at most 3 items, ranked by how much the student struggled (most missed first).
- If multiple wrong questions share the same topic, merge them into one entry.
- Explanations must be specific to the source material — not generic study advice.
- Return only the JSON array. No markdown, no explanation.\
"""

_QUESTION_TEMPLATE = """\
Context:
{context}

Question: {question}

{options}

Answer with only the letter (A, B, C, or D).\
"""


def _answer(client: anthropic.Anthropic, context: str, question: dict) -> str:
    options_text = "\n".join(question["options"])
    prompt = _QUESTION_TEMPLATE.format(
        context=context,
        question=question["question"],
        options=options_text,
    )
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip().upper()
    for ch in text:
        if ch in "ABCD":
            return ch
    return "?"


def _generate_focus_areas(
    client: anthropic.Anthropic,
    wrong_questions: list[dict],
    narration_context: str,
) -> list[dict]:
    if not wrong_questions:
        return []

    wrong_text = "\n".join(
        f"- Topic: {q.get('topic', 'Unknown')} | Question: {q['question']}"
        for q in wrong_questions
    )
    prompt = _FOCUS_USER_TEMPLATE.format(
        wrong_questions=wrong_text,
        narration=narration_context,
    )
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=_FOCUS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    try:
        areas = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return areas[:3] if isinstance(areas, list) else []


def evaluate_quiz(
    script: dict,
    pdf_text: str,
    questions: list[dict],
    user_answers: list[str] | None = None,
) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    client = anthropic.Anthropic(api_key=api_key)
    narration_context = "\n\n".join(s["narration"] for s in script.get("slides", []))

    results = []
    for q in questions:
        narration_answer = _answer(client, narration_context, q)
        full_source_answer = _answer(client, pdf_text, q)
        correct = q["answer"].upper()
        results.append({
            "question": q["question"],
            "correct_answer": correct,
            "narration_answer": narration_answer,
            "narration_correct": narration_answer == correct,
            "full_source_answer": full_source_answer,
            "full_source_correct": full_source_answer == correct,
        })

    out: dict = {
        "narration_score": sum(r["narration_correct"] for r in results),
        "full_source_score": sum(r["full_source_correct"] for r in results),
        "total_questions": len(results),
        "questions": results,
    }

    if user_answers is not None:
        wrong = [
            q for q, ua in zip(questions, user_answers)
            if ua.upper() != q["answer"].upper()
        ]
        out["focus_areas"] = _generate_focus_areas(client, wrong, narration_context)

    return out
