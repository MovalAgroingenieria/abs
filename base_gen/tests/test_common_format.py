# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import base64
from datetime import date as date_type

from odoo.tests.common import TransactionCase


class TestCommonFormat(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.common = cls.env["common.format"]

    # ----------------------------- numbers -----------------------------

    def test_transform_integer_to_locale(self):
        out = self.common.transform_integer_to_locale(12345)
        self.assertIsInstance(out, str)
        self.assertTrue(out)

    def test_transform_float_to_locale(self):
        out = self.common.transform_float_to_locale(12345.678, precision=2)
        self.assertIsInstance(out, str)
        self.assertTrue(out)
        self.assertRegex(out, r"[.,]68$")

    # ------------------------------ dates ------------------------------

    def test_transform_date_to_locale(self):
        d = date_type(2025, 1, 10)
        out = self.common.transform_date_to_locale(d, lang="en_US")
        self.assertIsInstance(out, str)
        self.assertTrue(out)

    def test_get_date_as_text_es(self):
        # Do not assume es_ES exists in the DB
        d = date_type(2025, 1, 10)
        out = self.common.get_date_as_text(d, with_year=True, lang="es_ES")
        self.assertIsInstance(out, str)
        self.assertTrue(out)
        self.assertIn("10", out)
        self.assertIn("2025", out)

    def test_get_date_as_text_en(self):
        d = date_type(2025, 1, 10)
        out = self.common.get_date_as_text(d, with_year=True, lang="en_US")
        self.assertIsInstance(out, str)
        self.assertTrue(out)
        self.assertIn("10", out)
        self.assertIn("2025", out)

    # --------------------------- translations --------------------------

    def test_get_value_from_translation_fallback(self):
        src = "NonexistentStringForSure"
        out = self.common.get_value_from_translation("base", src, lang="es_ES")
        self.assertIsInstance(out, str)
        # Either translated or fallback. For a made-up string it must be identical.
        self.assertEqual(out, src)

    def test_get_value_from_translation_invalid_inputs(self):
        self.assertEqual(self.common.get_value_from_translation(None, None, lang=None), "")
        self.assertEqual(self.common.get_value_from_translation("", "Hello", lang="en_US"), "Hello")
        self.assertEqual(self.common.get_value_from_translation("base", "", lang="en_US"), "")

    # ------------------------------ crypto -----------------------------

    def test_encrypt_data_cbc_block_and_key_sizes(self):
        key128 = "0123456789abcdef"
        b64_128 = self.common.encrypt_data(["user", "token"], key128)
        raw_128 = base64.b64decode(b64_128)
        self.assertEqual(len(raw_128) % 16, 0)

        key256 = "0123456789abcdef0123456789abcdef"
        b64_256 = self.common.encrypt_data(["a", "b", "c"], key256)
        raw_256 = base64.b64decode(b64_256)
        self.assertEqual(len(raw_256) % 16, 0)

        self.assertNotEqual(b64_128, b64_256)

    # ------------------------------ html -------------------------------

    def test_html_utils(self):
        self.assertFalse(self.common.is_html_field_filled(None))
        self.assertFalse(self.common.is_html_field_filled("<p>   </p>"))
        self.assertTrue(self.common.is_html_field_filled("<p>Hello World</p>"))

    def test_date_sanitization(self):
        cases = [
            ("%Y-%m-%d", "yyyy-MM-dd"),
            ("%d/%m/%Y", "dd/MM/yyyy"),
            ("", "yyyy-MM-dd"),
            (None, "yyyy-MM-dd"),
        ]
        for input_pattern, expected in cases:
            sanitized = self.common._sanitize_date_pattern(input_pattern)
            self.assertEqual(sanitized, expected)
