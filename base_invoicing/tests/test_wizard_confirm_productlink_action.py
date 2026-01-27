# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=invalid-name
from odoo.tests.common import TransactionCase


class TestWizardConfirmProductlinkAction(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Wizard = self.env["wizard.confirm.productlink.action"]

    def test_execute_operation_missing_context(self):
        wizard = self.Wizard.create({})
        res = wizard.execute_operation()
        self.assertFalse(res)

    def test_execute_operation_missing_operation(self):
        wizard = self.Wizard.with_context(active_id=1).create({})
        res = wizard.execute_operation()
        self.assertFalse(res)

    def test_execute_operation_missing_active_id(self):
        wizard = self.Wizard.with_context(operation="delete").create({})
        res = wizard.execute_operation()
        self.assertFalse(res)

    def test_execute_operation_record_not_found(self):
        wizard = self.Wizard.with_context(
            active_id=999999999,
            operation="delete",
        ).create({})
        res = wizard.execute_operation()
        self.assertFalse(res)
