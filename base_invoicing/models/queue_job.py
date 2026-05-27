# 2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=broad-exception-caught

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class QueueJob(models.Model):
    _inherit = "queue.job"

    def write(self, vals):
        """Propagate terminal queue.job states back to the linked invoiceset.

        The user never sees the queue.job: they manage everything from the
        invoice set form. We translate:

        - state='failed' (retries exhausted) -> invoiceset.state='error',
          and copy the traceback into ``last_calculation_error``.
        - state='done'   -> nothing (the job itself already finalized
          state='calculated'/'configured' in invoice_generation).
        - state='cancelled' -> nothing (cancel_invoices already reset
          the invoiceset to 'configured' before cancelling the job).
        """
        new_state = vals.get("state")
        if new_state != "failed":
            return super().write(vals)
        invoicesets_to_error = self._linked_invoicesets_for_failure()
        res = super().write(vals)
        if invoicesets_to_error:
            for job in self:
                if job.state != "failed":
                    continue
                invoiceset = invoicesets_to_error.get(job.id)
                if not invoiceset:
                    continue
                # Persist via raw SQL so the change survives even if the
                # surrounding transaction is later rolled back by queue_job.
                exc_info = job.exc_info or job.exc_message or ""
                self.env.cr.execute(
                    """
                    UPDATE account_invoiceset
                       SET state = 'error',
                           last_calculation_error = %s,
                           calculation_finished_at = NOW() AT TIME ZONE 'UTC',
                           invoice_generation_progress = 0.0,
                           write_date = NOW() AT TIME ZONE 'UTC'
                     WHERE id = %s
                    """,
                    (exc_info, invoiceset.id),
                )
                try:
                    invoiceset.message_post(
                        body=self.env._(
                            "Calculation Process: ERROR (background job "
                            "failed after retries). See the 'Calculation' "
                            "tab for the traceback."
                        )
                    )
                except Exception:  # noqa: BLE001
                    _logger.warning(
                        "Could not post chatter on invoiceset %s after "
                        "queue.job %s failure",
                        invoiceset.id,
                        job.uuid,
                    )
        return res

    def _linked_invoicesets_for_failure(self):
        """Return {job_id: invoiceset} for jobs about to transition to
        'failed' and that are linked to an invoiceset still in
        'calculating'. Used by :meth:`write` to update the invoiceset."""
        invoiceset_model = self.env["account.invoiceset"].sudo()
        result = {}
        for job in self:
            if job.state == "failed":
                continue
            invoiceset = invoiceset_model.search(
                [("queue_job_id", "=", job.id)], limit=1
            )
            if invoiceset and invoiceset.state == "calculating":
                result[job.id] = invoiceset
        return result
