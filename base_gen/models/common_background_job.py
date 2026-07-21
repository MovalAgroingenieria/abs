# 2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import models

_ACTIVE_JOB_STATES = ("wait_dependencies", "pending", "enqueued", "started")


class CommonBackgroundJob(models.AbstractModel):
    """Helper to launch deduplicated background (queue_job) actions.

    Mass "regenerate everything" technical actions must never run
    synchronously in the user's HTTP request: they should be delayed as
    a single background job. If a previous run is still
    pending/enqueued/running, no duplicate job is created and the user
    is notified instead.
    """

    _name = "common.background.job"
    _description = "Common helpers for deduplicated background jobs"

    def _is_background_job_running(self, job_key):
        """Return True if a job identified by ``job_key`` is in progress."""
        return bool(
            self.env["queue.job"]
            .sudo()
            .search_count(
                [
                    ("identity_key", "=", job_key),
                    ("state", "in", _ACTIVE_JOB_STATES),
                ]
            )
        )

    def _is_background_batch_running(self, batch_name):
        """Return True if a job batch named ``batch_name`` is not finished.

        Used to launch a mass action as many small (chunked) jobs grouped
        in a ``queue.job.batch``, so progress can be tracked via its
        ``completeness`` field, while still preventing a duplicate batch
        from being launched while a previous one is still running.
        """
        return bool(
            self.env["queue.job.batch"]
            .sudo()
            .search_count(
                [
                    ("name", "=", batch_name),
                    ("state", "!=", "finished"),
                ]
            )
        )

    def _new_background_batch(self, batch_name):
        """Create and return a new ``queue.job.batch`` named ``batch_name``."""
        return self.env["queue.job.batch"].sudo().get_new_batch(batch_name)

    def _background_job_notification(self, launched, from_backend):
        """Build the client notification about the background job status."""
        if not from_backend:
            return None
        if launched:
            title = self.env._("Generation queued")
            message = self.env._(
                "The generation has been queued and will run in the "
                "background. You can follow its progress in the Job "
                "Queue Batches menu (or the progress icon in the top bar)."
            )
            notify_type = "success"
        else:
            title = self.env._("Generation already in progress")
            message = self.env._(
                "A background generation is already in progress. Please "
                "wait for it to finish before launching another one."
            )
            notify_type = "warning"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": notify_type,
                "sticky": False,
            },
        }
