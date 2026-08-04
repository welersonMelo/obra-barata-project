"""Structured-output schema the LLM fills when answering the questionnaire."""

from pydantic import BaseModel, ConfigDict, Field

from app.models.question_models import ConfidenceLevel


class LLMAnswer(BaseModel):  # type: ignore[misc]
    """A single answer produced by the LLM for one question."""

    model_config = ConfigDict(populate_by_name=True)

    question_id: str = Field(description="The id of the question being answered.")
    answer: list[str] | None = Field(
        description=(
            "The answer as a list of strings, or null when confidence_level is 0. "
            "For open-ended questions, use a single element holding the full answer text. "
            "For multiple-choice questions, list the chosen option(s), each copied exactly "
            "from the provided options."
        ),
    )
    confidence_level: ConfidenceLevel = Field(
        alias="confidenceLevel",
        description=(
            "Evidence confidence for this answer. Use 0 when nothing relevant was found "
            "and answer must be null; 4 when inferred from context but not stated; "
            "7 when the answer exists in the context in other words; 10 when the exact "
            "answer text exists in the context."
        ),
    )


class LLMAnswerSet(BaseModel):  # type: ignore[misc]
    """The full set of answers produced by the LLM, one per question."""

    answers: list[LLMAnswer] = Field(
        description="One answer object for every question in the questionnaire.",
    )
