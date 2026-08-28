def run_quiz_with_context(context: str, quiz: list[dict]) -> dict:
    """Run quiz questions against an LLM given the provided context.

    Args:
        context: The text context to provide to the LLM (narration transcript
                 or full source PDF text).
        quiz: List of question dicts, each with keys:
              "question" (str), "choices" (list[str]), "answer_index" (int).

    Returns:
        Dict with keys "answers" (list[int]) and "score" (float 0.0–1.0).
    """
    ...


def compare_accuracy(narration_result: dict, full_source_result: dict) -> dict:
    """Compare quiz accuracy between narration-only and full-source contexts.

    Args:
        narration_result: Output of run_quiz_with_context() using narration text.
        full_source_result: Output of run_quiz_with_context() using full PDF text.

    Returns:
        Dict with keys "narration_score" (float), "full_source_score" (float),
        "delta" (float, full_source_score - narration_score).
    """
    ...


if __name__ == "__main__":
    pass
