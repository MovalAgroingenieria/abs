# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments

import logging
from typing import Dict, Optional

from odoo import models

_logger = logging.getLogger(__name__)

_LEVELS: Dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class CommonLog(models.AbstractModel):
    _name = "common.log"
    _description = "Common helpers for logging messages with optional context"

    _reserved_logrecord_attrs = {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
    }

    def _sanitize_extra(self, extra: Optional[dict]) -> dict:
        """Return a safe 'extra' dict for Python logging."""
        payload = dict(extra or {})
        # Drop reserved keys to avoid raising KeyError in logging internals
        for key in list(payload.keys()):
            if key in self._reserved_logrecord_attrs:
                payload.pop(key, None)
        return payload

    def register_in_log(
        self,
        message: str,
        source: str = "",
        module: str = "",
        model: str = "",
        method: str = "",
        message_type: str = "INFO",
        *,
        extra: Optional[dict] = None,
    ) -> None:
        """Log a message with optional context."""
        if not message:
            return

        level_name = (message_type or "INFO").upper()
        level = _LEVELS.get(level_name, logging.INFO)

        logger = logging.getLogger(source) if source else _logger

        parts = []
        if module:
            parts.append(f"module: {module}")
        if model:
            parts.append(f"model: {model}")
        if method:
            parts.append(f"method: {method}")

        msg = message if not parts else f"{message} ({', '.join(parts)})"

        payload = self._sanitize_extra(extra)
        if module:
            payload.setdefault("ctx_module", module)
        if model:
            payload.setdefault("ctx_model", model)
        if method:
            payload.setdefault("ctx_method", method)

        # Always pass a dict (logging expects mapping for 'extra')
        logger.log(level, msg, extra=payload)
