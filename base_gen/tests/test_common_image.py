# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=protected-access

import base64
import io

from PIL import Image

# Odoo test base (SavepointCase puede no existir en algunos builds)
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


def _img_rgba(size, color) -> Image.Image:
    """Create a solid RGBA image with given (w, h) and (r, g, b, a)."""
    return Image.new("RGBA", size, color)


def _to_png_bytes(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _to_b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


@tagged("-at_install", "post_install")
class TestCommonImage(SavepointCase):
    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        super().setUpClass()
        cls.common = cls.env["common.image"]

        # Background: opaque blue 64x48
        cls.bg = _img_rgba((64, 48), (0, 0, 255, 255))
        # Foreground: opaque red 16x12
        cls.fg_red = _img_rgba((16, 12), (255, 0, 0, 255))
        # Foreground: semi-transparent green 16x12 (alpha 128)
        cls.fg_green50 = _img_rgba((16, 12), (0, 255, 0, 128))

        cls.bg_bytes = _to_png_bytes(cls.bg)
        cls.fg_red_bytes = _to_png_bytes(cls.fg_red)
        cls.fg_green50_bytes = _to_png_bytes(cls.fg_green50)

        cls.bg_b64 = _to_b64(cls.bg_bytes)
        cls.fg_red_b64 = _to_b64(cls.fg_red_bytes)
        cls.fg_green50_b64 = _to_b64(cls.fg_green50_bytes)

        cls.bg_buf = io.BytesIO(cls.bg_bytes)
        cls.fg_red_buf = io.BytesIO(cls.fg_red_bytes)

    # ----------------------------- _as_image -----------------------------

    def test_as_image_accepts_bytes_base64_bytesio(self):
        # bytes
        im_b = self.common._as_image(self.bg_bytes)
        self.assertEqual(im_b.mode, "RGBA")
        self.assertEqual(im_b.size, (64, 48))

        # base64
        im_b64 = self.common._as_image(self.bg_b64)
        self.assertEqual(im_b64.mode, "RGBA")
        self.assertEqual(im_b64.size, (64, 48))

        # BytesIO
        im_buf = self.common._as_image(self.bg_buf)
        self.assertEqual(im_buf.mode, "RGBA")
        self.assertEqual(im_buf.size, (64, 48))

    def test_as_image_errors(self):
        with self.assertRaises(ValueError):
            self.common._as_image(None)
        with self.assertRaises(ValueError):
            self.common._as_image("**not base64**")
        with self.assertRaises(TypeError):
            self.common._as_image(123)  # type: ignore

    # ---------------------------- _dump_image ----------------------------

    def test_dump_image_base64_and_bytes(self):
        im = self.bg.copy()
        b64 = self.common._dump_image(im, out_format="PNG", return_base64=True)
        raw = base64.b64decode(b64)
        self.assertGreater(len(raw), 0)

        raw2 = self.common._dump_image(im, out_format="PNG", return_base64=False)
        self.assertIsInstance(raw2, (bytes, bytearray))
        self.assertGreater(len(raw2), 0)

    # ------------------------------ merge_img ---------------------------

    def _open_result(self, result) -> Image.Image:
        """Open returned image (bytes/base64) for assertions."""
        data = base64.b64decode(result) if isinstance(result, str) else result
        return Image.open(io.BytesIO(data))

    def test_merge_returns_none_when_missing_inputs(self):
        self.assertIsNone(self.common.merge_img(None, self.fg_red_b64))  # type: ignore
        self.assertIsNone(self.common.merge_img(self.bg_b64, None))  # type: ignore

    def test_merge_basic_overlay_position(self):
        # Paste red at (10, 5) over blue background
        res = self.common.merge_img(
            self.bg_b64,
            self.fg_red_b64,
            position=(10, 5),
            return_base64=True,
        )
        im = self._open_result(res)
        self.assertEqual(im.size, (64, 48))
        # PNG keeps alpha, but either RGBA/RGB is fine
        self.assertIn(im.mode, ("RGBA", "RGB"))

        # Pixel inside the pasted rect should be red
        px_inside = im.getpixel((10 + 1, 5 + 1))
        self.assertEqual(px_inside[:3], (255, 0, 0))

        # Pixel outside should be blue
        px_outside = im.getpixel((0, 0))
        self.assertEqual(px_outside[:3], (0, 0, 255))

    def test_merge_respects_alpha_mask(self):
        # Semi-transparent green over blue; inside should be a blend
        res = self.common.merge_img(self.bg_b64, self.fg_green50_b64, position=(8, 8))
        im = self._open_result(res)
        inside = im.getpixel((9, 9))[:3]
        self.assertNotEqual(inside, (0, 0, 255))  # not pure background
        self.assertNotEqual(inside, (0, 255, 0))  # not pure foreground

    def test_merge_fit_foreground_keep_aspect(self):
        # Make a tall foreground, fit into bg with keep_aspect=True
        fg_tall = _img_rgba((16, 64), (255, 0, 0, 255))
        res = self.common.merge_img(
            self.bg_bytes,
            _to_png_bytes(fg_tall),
            fit_foreground=True,
            keep_aspect=True,
            return_base64=False,
        )
        im = self._open_result(res)
        self.assertEqual(im.size, (64, 48))  # canvas equals background

    def test_merge_fit_foreground_stretch(self):
        # Stretch to exact bg size (keep_aspect=False)
        fg_small = _img_rgba((8, 8), (255, 0, 0, 255))
        res = self.common.merge_img(
            self.bg_buf,
            _to_png_bytes(fg_small),
            fit_foreground=True,
            keep_aspect=False,
            return_base64=True,
        )
        im = self._open_result(res)
        self.assertEqual(im.size, (64, 48))

    def test_merge_output_formats_png_and_jpeg(self):
        # PNG keeps alpha channel if present
        res_png = self.common.merge_img(
            self.bg_b64,
            self.fg_red_b64,
            format_output_img="PNG",
            return_base64=True,
        )
        im_png = self._open_result(res_png)
        self.assertIn(im_png.mode, ("RGBA", "RGB"))

        # JPEG flattens alpha → RGB
        res_jpg = self.common.merge_img(
            self.bg_b64,
            self.fg_red_b64,
            format_output_img="JPEG",
            return_base64=False,
        )
        im_jpg = self._open_result(res_jpg)
        self.assertEqual(im_jpg.mode, "RGB")
        self.assertEqual(im_jpg.size, (64, 48))
