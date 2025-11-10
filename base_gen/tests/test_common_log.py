# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
from contextlib import contextmanager

# Odoo test base
try:
    from odoo.tests.common import SavepointCase
except ImportError:  # pragma: no cover
    from odoo.tests.common import TransactionCase as SavepointCase

try:
    from odoo.tests.common import tagged
except ImportError:  # pragma: no cover
    try:
        from odoo.tests import tagged
    except ImportError:

        def tagged(*_tags):
            def _decorator(obj):
                return obj

            return _decorator


class _MemoryHandler(logging.Handler):
    """Simple in-memory handler to capture emitted LogRecords."""

    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        self.records = []

    def emit(self, record):
        self.records.append(record)


@contextmanager
def capture_logger(name, level=logging.DEBUG):
    """Attach a memory handler to a named logger during the context."""
    logger = logging.getLogger(name)
    old_level = logger.level
    logger.setLevel(level)
    handler = _MemoryHandler(level=level)
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)


@tagged("-at_install", "post_install")
class TestCommonLog(SavepointCase):
    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        super().setUpClass()
        cls.common = cls.env["common.log"]

    def test_logs_with_suffix_and_extra(self):
        """Emits WARNING with suffix and merged extra fields."""
        src = "moval.test.commonlog"
        base_msg = "Processing completed"
        module = "base_gen"
        model = "res.partner"
        method = "do_stuff"
        extra = {"request_id": "abc-123"}

        with capture_logger(src) as mem:
            self.common.register_in_log(
                base_msg,
                source=src,
                module=module,
                model=model,
                method=method,
                message_type="WARNING",
                extra=extra,
            )

        self.assertEqual(len(mem.records), 1, "One record should be emitted")
        rec = mem.records[0]
        self.assertEqual(rec.levelno, logging.WARNING)

        # Message must include human-readable suffix with context
        msg = rec.getMessage()
        self.assertIn(base_msg, msg)
        self.assertIn(f"module: {module}", msg)
        self.assertIn(f"model: {model}", msg)
        self.assertIn(f"method: {method}", msg)

        # Extra fields become attributes on the LogRecord
        self.assertEqual(getattr(rec, "request_id", None), "abc-123")
        self.assertEqual(getattr(rec, "ctx_module", None), module)
        self.assertEqual(getattr(rec, "ctx_model", None), model)
        self.assertEqual(getattr(rec, "ctx_method", None), method)

    def test_invalid_level_falls_back_to_info(self):
        """Invalid message_type should fallback to INFO."""
        src = "moval.test.commonlog.level"
        with capture_logger(src) as mem:
            self.common.register_in_log("Hello", source=src, message_type="NOPE")
        self.assertEqual(len(mem.records), 1)
        self.assertEqual(mem.records[0].levelno, logging.INFO)

    def test_empty_message_emits_nothing(self):
        """Empty message should not emit any record."""
        src = "moval.test.commonlog.empty"
        with capture_logger(src) as mem:
            self.common.register_in_log("", source=src)
        self.assertEqual(len(mem.records), 0)

    def test_uses_specified_source_logger(self):
        """Record should be emitted on the provided source logger."""
        src = "moval.test.commonlog.specific"
        other = "moval.test.commonlog.other"

        with capture_logger(src) as mem_src, capture_logger(other) as mem_other:
            self.common.register_in_log("Ping", source=src, message_type="DEBUG")

        self.assertEqual(len(mem_src.records), 1)
        # Ensure it did not go to 'other' by accident
        self.assertEqual(len(mem_other.records), 0)
