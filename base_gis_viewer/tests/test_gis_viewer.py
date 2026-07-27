# 2026 Moval Agroingenieria
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=invalid-name,protected-access
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestGisViewer(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env.company.write(
            {
                "gis_viewer_url": "https://example.test/gis",
                "gis_viewer_username": "user",
                "gis_viewer_password": "pass",
                "gis_viewer_cipher_key": "0123456789abcdef",
                "gis_viewer_previs_additional_args": "mode=min",
            }
        )

    def _new_record(self, **vals):
        """Create an in-memory gis.viewer record for GIS viewer tests.

        We use `new()` to avoid the need for access rights or a full
        administrative chain, which are not relevant for the viewer URL logic.
        """
        defaults = {"name": "P-001"}
        defaults.update(vals)
        return self.env["gis.viewer.test.model"].new(defaults)

    def test_compute_gis_code(self):
        rec = self._new_record(name="P-001")
        self.assertEqual(rec.gis_code, "P-001")

    def test_get_gis_link_empty_when_not_mapped(self):
        rec = self._new_record(name="P-001", mapped_to_polygon=False)
        self.assertEqual(rec._get_gis_link(public=True), "")

    def test_get_encrypted_credentials_returns_base64(self):
        rec = self._new_record(name="P-001", mapped_to_polygon=True)

        class _FakeSession:
            sid = "SID123"

        class _FakeRequest:
            session = _FakeSession()

        with patch(
            "odoo.addons.base_gis_viewer.models.gis_viewer.request", _FakeRequest()
        ):
            token = rec._get_encrypted_credentials()

        self.assertTrue(token)
        self.assertRegex(token, r"^[A-Za-z0-9+/=]+$")
        self.assertEqual(len(token) % 4, 0)

    def test_get_encrypted_credentials_empty_without_config(self):
        rec = self._new_record(name="P-001", mapped_to_polygon=True)
        self.env.company.write({"gis_viewer_username": "", "gis_viewer_password": ""})
        self.assertEqual(rec._get_encrypted_credentials(), "")
