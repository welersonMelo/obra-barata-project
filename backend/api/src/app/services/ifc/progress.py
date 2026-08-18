"""Progress logging helpers for IFC workflows."""

import logging
from time import perf_counter
from typing import Any


class StageProgressLogger:
    """Log the current workflow stage and duration of the previous one."""

    def __init__(
        self,
        workflow: str,
        logger: logging.Logger,
        **context: Any,
    ) -> None:
        self.workflow = workflow
        self.logger = logger
        self.context = context
        self.started_at = perf_counter()
        self.previous_stage = "inicio"
        self.previous_mark = self.started_at

    def step(self, current_stage: str, **context: Any) -> None:
        now = perf_counter()
        previous_duration = now - self.previous_mark
        merged_context = {**self.context, **context}
        self.logger.info(
            "IFC workflow=%s etapa_atual=%s etapa_anterior=%s "
            "duracao_etapa_anterior_s=%.3f %s",
            self.workflow,
            current_stage,
            self.previous_stage,
            previous_duration,
            self._format_context(merged_context),
        )
        self.previous_stage = current_stage
        self.previous_mark = now

    def finish(self, **context: Any) -> None:
        now = perf_counter()
        previous_duration = now - self.previous_mark
        total_duration = now - self.started_at
        merged_context = {**self.context, **context}
        self.logger.info(
            "IFC workflow=%s etapa_atual=concluido etapa_anterior=%s "
            "duracao_etapa_anterior_s=%.3f duracao_total_s=%.3f %s",
            self.workflow,
            self.previous_stage,
            previous_duration,
            total_duration,
            self._format_context(merged_context),
        )

    @staticmethod
    def _format_context(context: dict[str, Any]) -> str:
        if not context:
            return ""
        return " ".join(
            f"{key}={value}"
            for key, value in context.items()
            if value is not None
        )
