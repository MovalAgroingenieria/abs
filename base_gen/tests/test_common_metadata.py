# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from typing import Set

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
class TestCommonMetadata(SavepointCase):
    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        super().setUpClass()
        cls.meta = cls.env["common.metadata"]

    # ------------------------------- get_field -------------------------------

    def test_get_field_basic_char(self):
        """It should return metadata for a normal stored field."""
        info = self.meta.get_field("res.partner", "name")
        self.assertIsInstance(info, dict)
        self.assertEqual(info["model"], "res.partner")
        self.assertEqual(info["name"], "name")
        # ttype of partner.name is char
        self.assertEqual(info["ttype"], "char")
        # Common attrs must exist (even if None/False)
        for key in (
            "field_description",
            "required",
            "readonly",
            "store",
            "index",
            "copy",
        ):
            self.assertIn(key, info)

    def test_get_field_returns_none_when_not_found(self):
        """Unknown field should return None, not raise."""
        info = self.meta.get_field("res.partner", "nonexistent_xyz")
        self.assertIsNone(info)

    # ----------------------- get_models_with_many2one -------------------------

    def test_get_models_with_many2one_includes_referenced_first(self):
        """When include_model=True, the referenced model is first."""
        rs = self.meta.get_models_with_many2one("res.partner", include_model=True)
        # Should be a recordset (possibly empty, but in standard DB it's not)
        self.assertTrue(hasattr(rs, "mapped"))
        if rs:
            self.assertEqual(rs[0].model, "res.partner")

    def test_get_models_with_many2one_each_has_m2o_to_partner(self):
        """All returned models (except the first when included) have a Many2one
        to res.partner."""
        rs = self.meta.get_models_with_many2one("res.partner", include_model=False)
        # For each model, check at least one m2o field points to res.partner
        imf = self.env["ir.model.fields"].sudo()
        for m in rs:
            fields = imf.search(
                [
                    ("model_id", "=", m.id),
                    ("ttype", "=", "many2one"),
                    ("relation", "=", "res.partner"),
                ],
                limit=1,
            )
            self.assertTrue(
                fields,
                msg=f"{m.model} should have a many2one to res.partner",
            )

    # ------------------------------- get_fields -------------------------------

    def test_get_fields_char_includes_name(self):
        """Filtering by 'char' types should include partner.name."""
        out = self.meta.get_fields("res.partner", "char")
        # Convert to set for robust membership test
        names: Set[str] = {x["name"] for x in out}
        self.assertIn("name", names)

    def test_get_fields_multiple_types(self):
        """Comma-separated types should filter accordingly."""
        out = self.meta.get_fields("res.partner", "char,many2one")
        self.assertTrue(out)  # in standard DB there are plenty
        for item in out:
            # Check the field exists and matches one of the requested types
            fld = (
                self.env["ir.model.fields"]
                .sudo()
                .search(
                    [
                        ("model", "=", "res.partner"),
                        ("name", "=", item["name"]),
                    ],
                    limit=1,
                )
            )
            self.assertTrue(fld)
            self.assertIn(fld.ttype, {"char", "many2one"})

    # --------------------------- get_inherited_models -------------------------

    def test_get_inherited_models_excludes_self_and_has_no_dupes(self):
        """The result excludes the model itself and has no duplicates."""
        inherited = self.meta.get_inherited_models("res.partner")
        self.assertIsInstance(inherited, list)
        # No self
        self.assertNotIn("res.partner", inherited)
        # No duplicates
        self.assertEqual(len(inherited), len(set(inherited)))
        # In most DBs, partner inherits from several mixins; length should be >= 1
        self.assertGreaterEqual(len(inherited), 1)
