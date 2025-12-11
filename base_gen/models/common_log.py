# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments

import logging
from typing import Dict, Optional

from odoo import models

_LEVELS: Dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class CommonLog(models.AbstractModel):
    _name = "common.log"
    _description = "Common helpers for logging messages with optional context"

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
        """Log a message with optional context.

        Args:
            message: The main log message
            source: Logger source/name (defaults to __name__)
            module: Module name for context
            model: Model name for context
            method: Method name for context
            message_type: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            extra: Additional context data for the log record
        """
        if not message:
            return  # nothing to log

        level_name = (message_type or "INFO").upper()
        level = _LEVELS.get(level_name)
        if level is None:
            level_name = "INFO"
            level = logging.INFO

        logger = logging.getLogger(source or __name__)

        # Build human-readable suffix
        parts = []
        if module:
            parts.append(f"module: {module}")
        if model:
            parts.append(f"model: {model}")
        if method:
            parts.append(f"method: {method}")

        msg = message if not parts else f"{message} ({', '.join(parts)})"

        # Build safe extra payload (avoid LogRecord reserved attrs like 'module')
        payload = dict(extra or {})
        if module:
            payload.setdefault("ctx_module", module)
        if model:
            payload.setdefault("ctx_model", model)
        if method:
            payload.setdefault("ctx_method", method)

        # Ensure payload is None if empty to avoid logging issues
        log_extra = payload if payload else None

        # Log with appropriate level and extra context
        logger.log(level, msg, extra=log_extra)