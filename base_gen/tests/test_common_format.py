# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import base64
from datetime import date as _date

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


@tagged("-at_install", "post_install")
class TestCommonFormat(SavepointCase):
    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        super().setUpClass()
        cls.common = cls.env["common.format"]
        # Make sure langs exist/active if present; be tolerant if not installed
        for code in ("es_ES", "en_US"):
            try:
                lang = cls.env["res.lang"].search([("code", "=", code)], limit=1)
            except KeyError:
                continue
            if lang and not lang.active:
                lang.active = True

    # ----------------------------- numbers -----------------------------

    def test_transform_integer_to_locale(self):
        # 12_345 should be grouped; exact separator depends on lang
        out_es = self.common.transform_integer_to_locale(12345, lang="es_ES")
        out_en = self.common.transform_integer_to_locale(12345, lang="en_US")
        self.assertRegex(out_es, r"^12[., ]?345$")
        self.assertRegex(out_en, r"^12[., ]?345$")
        self.assertNotEqual(out_es, out_en, "Locales should differ in formatting")

    def test_transform_float_to_locale(self):
        out_es = self.common.transform_float_to_locale(
            12345.678, precision=2, lang="es_ES"
        )
        out_en = self.common.transform_float_to_locale(
            12345.678, precision=2, lang="en_US"
        )
        # v18 rounds to .68 with grouping; just assert the decimals
        self.assertRegex(out_es, r"[.,]68$")
        self.assertRegex(out_en, r"[.,]68$")
        self.assertNotEqual(out_es, out_en)

    # ------------------------------ dates ------------------------------

    def test_transform_date_to_locale(self):
        d = _date(2025, 1, 10)
        es = self.common.transform_date_to_locale(d, lang="es_ES")
        en = self.common.transform_date_to_locale(d, lang="en_US")
        # Should return non-empty localized strings; allow same string if formats equal
        self.assertIsInstance(es, str)
        self.assertTrue(es)
        self.assertIsInstance(en, str)
        self.assertTrue(en)

    def test_get_date_as_text_es(self):
        d = _date(2025, 1, 10)
        txt = self.common.get_date_as_text(d, with_year=True, lang="es_ES")
        self.assertIn("10", txt)
        self.assertIn("2025", txt)
        self.assertRegex(
            txt,
            r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|"
            r"octubre|noviembre|diciembre)",
        )

    def test_get_date_as_text_en(self):
        d = _date(2025, 1, 10)
        txt = self.common.get_date_as_text(d, with_year=True, lang="en_US")
        self.assertIn("10", txt)
        self.assertIn("2025", txt)
        self.assertRegex(
            txt,
            r"(January|February|March|April|May|June|July|August|"
            r"September|October|November|December)",
        )

    # --------------------------- translations --------------------------

    def test_get_value_from_translation(self):
        # If ir.translation is not available in this run, skip the test
        try:
            self.env["ir.translation"]
        except KeyError:
            self.skipTest("ir.translation model not available in this test run")

        module = "test_common_format"
        src = "Hello"
        lang = "es_ES"
        val = "Hola"

        self.env["ir.translation"].sudo().create(
            {
                "name": "common.format,help",
                "lang": lang,
                "type": "model",
                "src": src,
                "value": val,
                "module": module,
            }
        )

        out = self.common.get_value_from_translation(module, src, lang=lang)
        self.assertEqual(out, val)
        out2 = self.common.get_value_from_translation(module, src, lang="fr_FR")
        self.assertEqual(out2, src)

    # ------------------------------ crypto -----------------------------

    def test_encrypt_data_cbc_block_and_key_sizes(self):
        # AES-128
        key128 = "0123456789abcdef"  # 16 bytes
        b64_128 = self.common.encrypt_data(["user", "token"], key128)
        raw_128 = base64.b64decode(b64_128)
        self.assertEqual(len(raw_128) % 16, 0)

        # AES-256
        key256 = "0123456789abcdef0123456789abcdef"  # 32 bytes
        b64_256 = self.common.encrypt_data(["a", "b", "c"], key256)
        raw_256 = base64.b64decode(b64_256)
        self.assertEqual(len(raw_256) % 16, 0)

        # different inputs/keys should reasonably change ciphertext
        self.assertNotEqual(b64_128, b64_256)
