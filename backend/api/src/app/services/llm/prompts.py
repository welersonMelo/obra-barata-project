"""Prompt construction for LLM-based questionnaire answering."""

from app.models.question_models import Question

SYSTEM_PROMPT = (
    "You are a research analyst. You receive text content extracted from a "
    "company source together with a fixed questionnaire, and your job is to "
    "fill in the questionnaire as accurately as possible.\n\n"
    "Rules:\n"
    "- Answer every question. Never skip one.\n"
    "- Base every answer on the provided source content; do not state facts "
    "that contradict it.\n"
    "- For every question, return an answer plus confidenceLevel using "
    "exactly one of these values: 0, 4, 7, or 10.\n"
    "- Use confidenceLevel 0 when nothing relevant to the question was "
    "found; in that case the answer must be null.\n"
    "- Use confidenceLevel 4 when the answer is inferred from context "
    "but is not stated in it.\n"
    "- Use confidenceLevel 7 when the answer exists in the context but "
    "in other words.\n"
    "- Use confidenceLevel 10 when the exact answer text exists in the "
    "context.\n"
    "- For multiple-choice questions, choose only the provided options, "
    "copying option text exactly. Pick a single option unless the question "
    "allows multiple; when it does, pick every option that applies while "
    "respecting the maximum selection limit when one is provided.\n"
    "- For open-ended questions, stay within the character limit when one is "
    "given.\n"
    "- Write each answer in the same language as the question text.\n"
    "- Return answers in the requested structured format, one entry per "
    "question, each carrying the matching question id."
)

_EMPTY_CONTENT_PLACEHOLDER = "(no textual content could be extracted from the source)"


def render_questions_block(questions: list[Question]) -> str:
    """Render the questionnaire as a human-readable, numbered block."""
    return "\n".join(
        _render_question_block(index, question)
        for index, question in enumerate(questions, start=1)
    )


def _render_question_block(index: int, question: Question) -> str:
    lines = [f"{index}. [id={question.id}] ({question.type}) {question.text}"]
    detail = _render_question_detail(question)
    if detail is not None:
        lines.append(detail)
    return "\n".join(lines)


def _render_question_detail(question: Question) -> str | None:
    if question.type == "multiple-choice":
        return _render_multiple_choice_detail(question)
    if question.type == "open-ended":
        return _render_open_ended_detail(question)
    return None


def _render_multiple_choice_detail(question: Question) -> str | None:
    if not question.options:
        return None
    if question.allow_multiple:
        selection = "one or more"
        if question.max_selections is not None:
            selection = f"one or more, up to {question.max_selections}"
    else:
        selection = "exactly one"
    return f"   Choose {selection} of: {' | '.join(question.options)}"


def _render_open_ended_detail(question: Question) -> str | None:
    if not question.max_chars_in_answer:
        return None
    return (
        "   Open-ended answer, at most "
        f"{question.max_chars_in_answer} characters."
    )


def build_human_message(
    url: str,
    company_name: str | None,
    content: str,
    questions: list[Question],
    source_label: str = "WEBSITE CONTENT",
) -> str:
    """Build the human message carrying source content and the questions."""
    return (
        f"Company website: {url}\n"
        f"Company name (from page metadata): {company_name or 'unknown'}\n\n"
        f"--- {source_label} (may be truncated) ---\n"
        f"{content.strip() or _EMPTY_CONTENT_PLACEHOLDER}\n"
        f"--- END OF {source_label} ---\n\n"
        "Answer the following questionnaire:\n"
        f"{render_questions_block(questions)}"
    )
