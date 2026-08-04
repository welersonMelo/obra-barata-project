"""Generation of questionnaire answers from scraped content using an LLM."""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.models.question_models import (
    ConfidenceLevel,
    GeneratedAnswer,
    Question,
    QuestionnaireFile,
)
from app.services.llm import prompts
from app.services.llm.client import build_chat_model
from app.services.llm.schemas import LLMAnswerSet
from app.settings import get_settings


def _match_options(values: list[str], options: list[str]) -> list[str]:
    """Map raw values to canonical option strings, case-insensitive and deduped."""
    lookup = {option.casefold(): option for option in options}
    matched: list[str] = []
    for value in values:
        canonical = lookup.get(value.casefold())
        if canonical is None:
            normalized = value.casefold()
            canonical = next(
                (
                    option
                    for option in options
                    if normalized in option.casefold() or option.casefold() in normalized
                ),
                None,
            )
        if canonical is not None and canonical not in matched:
            matched.append(canonical)
    return matched


def _coerce_answer(question: Question, values: list[str]) -> str | list[str]:
    """Coerce raw LLM values to the answer shape expected by question type."""
    cleaned = [value.strip() for value in values if value and value.strip()]
    if question.type == "multiple-choice":
        return _coerce_multiple_choice_answer(question, cleaned)
    return _coerce_open_ended_answer(question, cleaned)


def _coerce_multiple_choice_answer(
    question: Question,
    values: list[str],
) -> str | list[str]:
    matched = _match_options(values, question.options or [])
    if question.allow_multiple:
        if question.max_selections is not None:
            return matched[: question.max_selections]
        return matched
    if not matched:
        return ""
    return matched[0]


def _coerce_open_ended_answer(question: Question, values: list[str]) -> str:
    text = " ".join(values)
    if question.max_chars_in_answer is None:
        return text
    return text[: question.max_chars_in_answer]


def _has_answer(answer: str | list[str]) -> bool:
    if isinstance(answer, list):
        return bool(answer)
    return bool(answer.strip())


class AnswerGenerator:
    """Generate answers to the predefined questionnaire."""

    def __init__(self, chat_model: BaseChatModel | None = None) -> None:
        """Initialize the generator with an optional injected chat model."""
        self._chat_model = chat_model

    async def generate(
        self,
        url: str,
        company_name: str | None,
        content: str,
        questionnaire: QuestionnaireFile,
        source_label: str = "WEBSITE CONTENT",
    ) -> list[GeneratedAnswer]:
        """Ask the LLM to answer the questionnaire and normalize the result."""
        model = self._chat_model or build_chat_model()
        structured_model = model.with_structured_output(LLMAnswerSet)
        max_chars = get_settings().LLM_MAX_CONTENT_CHARS
        messages = [
            SystemMessage(content=prompts.SYSTEM_PROMPT),
            HumanMessage(
                content=prompts.build_human_message(
                    url=url,
                    company_name=company_name,
                    content=content[:max_chars],
                    questions=questionnaire.questions,
                    source_label=source_label,
                ),
            ),
        ]
        raw = await structured_model.ainvoke(messages)
        answer_set = LLMAnswerSet.model_validate(raw)
        return self._normalize(answer_set, questionnaire.questions)

    @staticmethod
    def _normalize(
        answer_set: LLMAnswerSet,
        questions: list[Question],
    ) -> list[GeneratedAnswer]:
        """Build generated answers in questionnaire order."""
        by_id = {answer.question_id: answer for answer in answer_set.answers}
        generated: list[GeneratedAnswer] = []
        for question in questions:
            raw_answer = by_id.get(question.id)
            if raw_answer is None or raw_answer.confidence_level == 0:
                generated.append(
                    GeneratedAnswer(
                        question_id=question.id,
                        answer=None,
                        confidence_level=0,
                    ),
                )
                continue

            values = list(raw_answer.answer or [])
            coerced = _coerce_answer(question, values)
            confidence_level: ConfidenceLevel = raw_answer.confidence_level
            if not _has_answer(coerced):
                generated.append(
                    GeneratedAnswer(
                        question_id=question.id,
                        answer=None,
                        confidence_level=0,
                    ),
                )
                continue

            generated.append(
                GeneratedAnswer(
                    question_id=question.id,
                    answer=coerced,
                    confidence_level=confidence_level,
                ),
            )
        return generated
