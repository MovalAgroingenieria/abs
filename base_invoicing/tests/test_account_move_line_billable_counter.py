# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestAccountMoveLineBillableCounter(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Move = cls.env["account.move"]
        cls.MoveLine = cls.env["account.move.line"]
        cls.Journal = cls.env["account.journal"]
        cls.Account = cls.env["account.account"]
        cls.BillableTest = cls.env["base_invoicing.billable_item_test"]

        cls.company = cls.env.company

        cls.journal = cls.Journal.search(
            [("company_id", "=", cls.company.id), ("type", "=", "general")],
            limit=1,
        )
        if not cls.journal:
            cls.journal = cls.Journal.search(
                [("company_id", "=", cls.company.id)],
                limit=1,
            )

        cls.account = cls.Account.search(
            [],
            limit=1,
        )

    def _create_move(self):

        return self.Move.create(
            {
                "move_type": "entry",
                "journal_id": self.journal.id,
            }
        )

    def test_update_billable_item_invoice_count_create_and_unlink(self):
        item = self.BillableTest.create({})
        self.assertEqual(item.number_of_invoices, 0)

        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "date": fields.Date.today(),
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "debit",
                            "account_id": self.account_debit.id,
                            "debit": 100.0,
                            "credit": 0.0,
                            "billable_item_model": self.item1._name,
                            "billable_item_res_id": self.item1.id,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "credit",
                            "account_id": self.account_credit.id,
                            "debit": 0.0,
                            "credit": 100.0,
                        },
                    ),
                ],
            }
        )
        move.action_post()
        line = move.line_ids.filtered(lambda l: l.billable_item_res_id == self.item1.id)

        item.invalidate_recordset(["number_of_invoices"])
        self.assertEqual(item.number_of_invoices, 1)

        line.unlink()
        item.invalidate_recordset(["number_of_invoices"])
        self.assertEqual(item.number_of_invoices, 0)

    def test_update_billable_item_invoice_count_never_below_zero(self):
        item = self.BillableTest.create({"partner_id": 1})
        self.assertEqual(item.number_of_invoices, 0)

        move = self._create_move()

        line = self.MoveLine.create(
            {
                "move_id": move.id,
                "name": "L1",
                "account_id": self.account.id,
                "debit": 10.0,
                "credit": 10.0,
                "billable_item_model": "base_invoicing.billable_item_test",
                "billable_item_res_id": item.id,
            }
        )
        line_id = line.id
        line.unlink()
        self.env["account.move.line"].browse(
            line_id
        ).unlink()  # recordset vacío -> no-op real

        self.assertGreaterEqual(item.number_of_invoices, 0)
