# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestCommonLog(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Log = cls.env["common.log"]

    def test_register_in_log_skips_empty_message(self):
        with patch("logging.getLogger") as get_logger:
            self.Log.register_in_log("")
            get_logger.assert_not_called()

    def test_register_in_log_default_level_and_context(self):
        with patch("logging.getLogger") as get_logger:
            logger = get_logger.return_value
            self.Log.register_in_log(
                "Hello",
                source="base_gen.test",
                module="base_gen",
                model="x.model",
                method="do",
                message_type="INFO",
                extra={"foo": "bar"},
            )

            logger.log.assert_called()
            level, msg = logger.log.call_args[0][:2]
            kwargs = logger.log.call_args.kwargs

            self.assertEqual(level, 20)  # INFO
            self.assertIn("Hello", msg)
            self.assertIn("module: base_gen", msg)
            self.assertIn("model: x.model", msg)
            self.assertIn("method: do", msg)

            self.assertIn("extra", kwargs)
            self.assertEqual(kwargs["extra"]["foo"], "bar")
            self.assertEqual(kwargs["extra"]["ctx_module"], "base_gen")
            self.assertEqual(kwargs["extra"]["ctx_model"], "x.model")
            self.assertEqual(kwargs["extra"]["ctx_method"], "do")

    def test_register_in_log_sanitizes_reserved_keys(self):
        with patch("logging.getLogger") as get_logger:
            logger = get_logger.return_value
            self.Log.register_in_log(
                "Hello",
                source="base_gen.test",
                extra={"module": "evil", "msg": "evil", "ok": 1},
            )
            kwargs = logger.log.call_args.kwargs
            extra = kwargs["extra"]
            self.assertNotIn("module", extra)
            self.assertNotIn("msg", extra)
            self.assertEqual(extra["ok"], 1)
