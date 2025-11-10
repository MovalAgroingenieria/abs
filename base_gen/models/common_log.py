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
            message: The log message (required).
            source: Logger name; defaults to this module's logger.
            module: Optional module name to append (business context).
            model: Optional model name to append (business context).
            method: Optional method name to append (business context).
            message_type: One of DEBUG/INFO/WARNING/ERROR/CRITICAL.
            extra: Structured fields passed to logging (appear in record.extra).

        Notes:
            - `extra` is useful for JSON logging handlers or for attaching
              correlation ids (e.g., request_id, partner_id, move_id).
            - When `module`/`model`/`method` are provided, they are also added
              into `extra` and appended to the message suffix for readability.
        """
        if not message:
            return  # nothing to log

        level_name = (message_type or "INFO").upper()
        level = _LEVELS.get(level_name)
        if level is None:
            # Fallback to INFO on invalid level names
            level_name = "INFO"
            level = logging.INFO

        logger = logging.getLogger(source or __name__)

        # Build human-readable suffix and normalized extra payload
        parts = []
        payload = dict(extra or {})
        if module:
            parts.append(f"module: {module}")
            payload.setdefault("module", module)
        if model:
            parts.append(f"model: {model}")
            payload.setdefault("model", model)
        if method:
            parts.append(f"method: {method}")
            payload.setdefault("method", method)

        msg = message
        if parts:
            msg = f"{message} ({', '.join(parts)})"

        # Emit log with selected level
        logger.log(level, msg, extra=payload or None)
