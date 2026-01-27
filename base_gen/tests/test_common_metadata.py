# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.tests.common import TransactionCase


class TestCommonMetadata(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Meta = cls.env["common.metadata"]

    def test_get_field_returns_metadata(self):
        meta = self.Meta.get_field("res.lang", "code", exclude_nonpersistent=True)
        self.assertTrue(meta)
        self.assertEqual(meta["model"], "res.lang")
        self.assertEqual(meta["name"], "code")
        self.assertTrue(meta["ttype"])

    def test_get_field_missing_returns_none(self):
        meta = self.Meta.get_field("res.lang", "field_does_not_exist")
        self.assertIsNone(meta)

    def test_get_fields_filters_types(self):
        fields = self.Meta.get_fields("res.lang", "char")
        self.assertTrue(isinstance(fields, list))
        self.assertTrue(any(f["name"] == "code" for f in fields))

    def test_get_models_with_many2one(self):
        # Many models have a Many2one to res.lang (lang field is often char though),
        # so use a target that is commonly referenced by m2o: res.company
        models_rs = self.Meta.get_models_with_many2one("res.company", include_model=True)
        self.assertTrue(models_rs)
        self.assertTrue(any(m.model == "res.company" for m in models_rs))

    def test_get_inherited_models_unknown(self):
        self.assertEqual(self.Meta.get_inherited_models("x.model.does.not.exist"), [])

    def test_get_inherited_models_returns_list(self):
        inherited = self.Meta.get_inherited_models("res.users")
        self.assertTrue(isinstance(inherited, list))
