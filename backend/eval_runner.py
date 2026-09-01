import os

import anthropic

_SYSTEM_PROMPT = (
    "You are a student taking a multiple-choice quiz. "
    "Read the context carefully and answer based only on what it contains. "
    "Reply with a single letter: A, B, C, or D. Nothing else."
)

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
    return response.content[0].text.strip().upper()[:1]


def evaluate_quiz(script: dict, pdf_text: str, questions: list[dict]) -> dict:
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

    return {
        "narration_score": sum(r["narration_correct"] for r in results),
        "full_source_score": sum(r["full_source_correct"] for r in results),
        "total_questions": len(results),
        "questions": results,
    }
