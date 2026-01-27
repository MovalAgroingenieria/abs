# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=protected-access

from odoo.tests.common import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestAccountMoveLineBillableCounter(TransactionCase):
    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        super().setUpClass()
        cls.Move = cls.env["account.move"]
        cls.MoveLine = cls.env["account.move.line"]
        cls.Journal = cls.env["account.journal"]
        cls.Account = cls.env["account.account"]
        cls.BillableTest = cls.env["base_invoicing.billable_item_test"]
        cls.Partner = cls.env["res.partner"]

        cls.company = cls.env.company
        cls.partner = cls.Partner.create({"name": "Test Partner"})

        cls.journal = cls.Journal.search(
            [("company_id", "=", cls.company.id), ("type", "=", "general")],
            limit=1,
        )
        if not cls.journal:
            cls.journal = cls.Journal.create(
                {
                    "name": "Test Journal",
                    "code": "TJ1",
                    "type": "general",
                    "company_id": cls.company.id,
                }
            )

        cls.account_debit = cls.Account.create(
            {
                "name": "Test Debit",
                "code": "TDEB1",
                "account_type": "asset_current",
            }
        )
        cls.account_credit = cls.Account.create(
            {
                "name": "Test Credit",
                "code": "TCRE1",
                "account_type": "liability_current",
            }
        )

    def _create_balanced_move_with_billable_line(self, item, amount=100.0):
        return self.Move.create(
            {
                "move_type": "entry",
                "journal_id": self.journal.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "debit",
                            "account_id": self.account_debit.id,
                            "debit": amount,
                            "credit": 0.0,
                            "billable_item_model": item._name,
                            "billable_item_res_id": item.id,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "credit",
                            "account_id": self.account_credit.id,
                            "debit": 0.0,
                            "credit": amount,
                        },
                    ),
                ],
            }
        )

    def test_update_billable_item_invoice_count_create_and_unlink(self):
        item = self.BillableTest.create({"partner_id": self.partner.id})
        self.assertEqual(item.number_of_invoices, 0)

        move = self._create_balanced_move_with_billable_line(item)
        line = move.line_ids.filtered(
            lambda my_line: my_line.billable_item_model == item._name
            and (
                my_line.billable_item_res_id.id
                if hasattr(my_line.billable_item_res_id, "id")
                else my_line.billable_item_res_id
            )
            == item.id
        )

        item.invalidate_recordset(["number_of_invoices"])
        self.assertEqual(item.number_of_invoices, 1)

        move.action_post()
        self.assertEqual(move.state, "posted")

        move.button_draft()
        self.assertEqual(move.state, "draft")
        move = line.move_id
        (move.line_ids).unlink()
        item.invalidate_recordset(["number_of_invoices"])
        self.assertEqual(item.number_of_invoices, 0)

    def test_update_billable_item_invoice_count_never_below_zero(self):
        item = self.BillableTest.create({"partner_id": self.partner.id})
        self.assertEqual(item.number_of_invoices, 0)

        move = self._create_balanced_move_with_billable_line(item, amount=10.0)
        line = move.line_ids.filtered(
            lambda my_line: my_line.billable_item_model == item._name
            and (
                my_line.billable_item_res_id.id
                if hasattr(my_line.billable_item_res_id, "id")
                else my_line.billable_item_res_id
            )
            == item.id
        )

        line_id = line.id
        move.action_post()
        self.assertEqual(move.state, "posted")

        move.button_draft()
        self.assertEqual(move.state, "draft")
        move = line.move_id
        (move.line_ids).unlink()
        # second unlink must be a real no-op
        self.env["account.move.line"].browse(line_id).exists().unlink()

        item.invalidate_recordset(["number_of_invoices"])
        self.assertGreaterEqual(item.number_of_invoices, 0)
