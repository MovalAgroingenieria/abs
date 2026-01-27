# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import base64
import io

from odoo.tests.common import TransactionCase
from PIL import Image


class TestCommonImage(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ImageHelper = cls.env["common.image"]

    def _png_bytes(self, size=(50, 50), rgba=(255, 0, 0, 128)):
        im = Image.new("RGBA", size, rgba)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        return buf.getvalue()

    def test_merge_img_returns_base64(self):
        bg = self._png_bytes(size=(60, 60), rgba=(0, 0, 255, 255))
        fg = self._png_bytes(size=(20, 20), rgba=(255, 0, 0, 128))

        out = self.ImageHelper.merge_img(bg, fg, format_output_img="PNG", return_base64=True)
        self.assertTrue(out)
        self.assertTrue(isinstance(out, str))
        # Ensure it is valid base64
        base64.b64decode(out.encode("ascii"))

    def test_merge_img_invalid_input_returns_none(self):
        out = self.ImageHelper.merge_img(None, None)
        self.assertIsNone(out)

        out = self.ImageHelper.merge_img("not_base64", "not_base64")
        self.assertIsNone(out)

    def test_merge_img_fit_foreground_keep_aspect(self):
        bg = self._png_bytes(size=(100, 50), rgba=(0, 0, 0, 255))
        fg = self._png_bytes(size=(50, 200), rgba=(255, 0, 0, 128))

        out_b64 = self.ImageHelper.merge_img(bg, fg, fit_foreground=True, keep_aspect=True)
        data = base64.b64decode(out_b64.encode("ascii"))
        im = Image.open(io.BytesIO(data))
        self.assertEqual(im.size, (100, 50))

    def test_dump_jpeg_flattens_alpha(self):
        bg = self._png_bytes(size=(40, 40), rgba=(0, 0, 0, 255))
        fg = self._png_bytes(size=(20, 20), rgba=(255, 0, 0, 128))

        out_b64 = self.ImageHelper.merge_img(bg, fg, format_output_img="JPEG", return_base64=True)
        data = base64.b64decode(out_b64.encode("ascii"))
        im = Image.open(io.BytesIO(data))
        self.assertIn(im.mode, ("RGB", "L"))
