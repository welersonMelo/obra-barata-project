"""Per-request file logging for supplier-pricing endpoint calls."""

from __future__ import annotations

import logging
import tempfile
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Iterator

from app.settings import get_settings


_current_pricing_log_path: ContextVar[Path | None] = ContextVar(
    "current_pricing_log_path",
    default=None,
)
_handler_lock = Lock()
_handler_installed = False


class PricingRequestFileHandler(logging.Handler):
    """Write log records to the active pricing request log file."""

    def emit(self, record: logging.LogRecord) -> None:
        log_path = _current_pricing_log_path.get()
        if log_path is None:
            return
        try:
            message = self.format(record)
            with log_path.open("a", encoding="utf-8") as log_file:
                log_file.write(message)
                log_file.write("\n")
        except Exception:
            self.handleError(record)


def ensure_pricing_request_log_handler() -> None:
    """Install the app logger handler once."""

    global _handler_installed
    if _handler_installed:
        return
    with _handler_lock:
        if _handler_installed:
            return
        handler = PricingRequestFileHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        logging.getLogger("app").addHandler(handler)
        _handler_installed = True


def _create_log_file_in(directory: Path, now: datetime) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / f"{now:%Y-%m-%d_%H-%M-%S-%f}.log"
    log_path.touch(exist_ok=False)
    return log_path


def create_pricing_request_log_file(now: datetime | None = None) -> Path:
    """Create a timestamp-named log file for one buscar_fornecedores call."""

    timestamp = now or datetime.now()
    configured_directory = get_settings().PRICING_REQUEST_LOG_DIR
    try:
        return _create_log_file_in(configured_directory, timestamp)
    except OSError:
        fallback_directory = (
            Path(tempfile.gettempdir()) / "obra-barata" / "buscar_fornecedores"
        )
        return _create_log_file_in(fallback_directory, timestamp)


@contextmanager
def pricing_request_log_context(log_path: Path) -> Iterator[None]:
    """Route app logs emitted in this context to log_path."""

    token = _current_pricing_log_path.set(log_path)
    try:
        yield
    finally:
        _current_pricing_log_path.reset(token)
