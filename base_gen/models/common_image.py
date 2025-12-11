# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=too-many-arguments

import base64
import io
from typing import Optional, Tuple, Union

from odoo import models
from PIL import Image, ImageOps

BinaryLike = Union[bytes, bytearray, str, io.BytesIO]
Point = Tuple[int, int]


class CommonImage(models.AbstractModel):
    _name = "common.image"
    _description = "Common helpers for image processing/compositing"

    # ------------------------------- utils --------------------------------

    def _as_image(self, payload: BinaryLike) -> Image.Image:
        """Load a PIL Image from bytes / base64 str / BytesIO."""
        if payload is None:
            raise ValueError("Empty image payload.")
        if isinstance(payload, io.BytesIO):
            buf = payload
        elif isinstance(payload, (bytes, bytearray)):
            buf = io.BytesIO(payload)
        elif isinstance(payload, str):
            # most Odoo binary fields deliver base64-encoded strings
            try:
                buf = io.BytesIO(base64.b64decode(payload))
            except Exception as exc:
                raise ValueError("String payload is not valid base64.") from exc
        else:
            raise TypeError("Unsupported image payload type.")

        with Image.open(buf) as im:
            # .copy() to detach from buffer; ensure RGBA for alpha-composite
            # Use Image.Resampling.LANCZOS for Pillow >= 10.0.0
            return im.convert("RGBA").copy()

    def _dump_image(
            self,
            image: Image.Image,
            out_format: str = "PNG",
            return_base64: bool = True,
            jpeg_background: Tuple[int, int, int] = (255, 255, 255),
    ) -> Union[bytes, io.BytesIO, str]:
        """Serialize PIL Image to bytes/base64 for Odoo binary fields.

        - PNG/WebP admiten alpha; JPEG no.
        - Si el formato es JPEG/JPG y la imagen tiene alpha, se aplana sobre
          `jpeg_background` (blanco por defecto).
        """
        fmt = (out_format or "PNG").upper()
        im = image

        if fmt in {"JPEG", "JPG"}:
            # Flatten alpha if present
            if im.mode in {"RGBA", "LA"}:
                bg = Image.new("RGB", im.size, jpeg_background)
                # Use alpha channel as mask
                alpha = im.split()[-1]  # last channel (A)
                bg.paste(im.convert("RGBA"), mask=alpha)
                im = bg
            elif im.mode not in {"RGB", "L"}:
                im = im.convert("RGB")

        out = io.BytesIO()
        # Optional: quality parameters without breaking PNG
        save_kwargs = {}
        if fmt in {"JPEG", "JPG"}:
            save_kwargs.update({"quality": 95, "subsampling": 0, "optimize": True})

        try:
            im.save(out, format=fmt, **save_kwargs)
        except KeyError:
            # Format not supported, fallback to PNG
            if fmt != "PNG":
                # Log warning or handle gracefully
                # self.env.cr.logger.warning(f"Format {fmt} not supported, falling back to PNG")
                fmt = "PNG"
                out = io.BytesIO()  # Reset buffer
                im.save(out, format=fmt, **save_kwargs)
            else:
                raise

        data = out.getvalue()
        return base64.b64encode(data).decode("ascii") if return_base64 else data

    # ----------------------------- public API -----------------------------

    def merge_img(
            self,
            background_img: BinaryLike,
            foreground_png: BinaryLike,
            *,
            format_output_img: str = "PNG",
            position: Point = (0, 0),
            fit_foreground: bool = False,
            keep_aspect: bool = True,
            return_base64: bool = True,
    ) -> Optional[Union[str, bytes]]:
        """Alpha-composite the foreground over the background.

        Args:
            background_img: bytes/base64/BytesIO of the background image.
            foreground_png: bytes/base64/BytesIO of the foreground (with alpha).
            format_output_img: output format (e.g. 'PNG', 'JPEG').
            position: (x, y) where the foreground's top-left corner is pasted.
            fit_foreground: if True, resize foreground to match the background size.
            keep_aspect: when fitting, preserve aspect ratio (letterbox/pad).
            return_base64: if True, return a base64 string (recommended for Binary fields).

        Returns:
            A base64 string (default) or raw bytes of the merged image.
            Returns None if any input is missing or invalid.
        """
        if not background_img or not foreground_png:
            return None

        try:
            bg = self._as_image(background_img)  # RGBA
            fg = self._as_image(foreground_png)  # RGBA
        except (ValueError, TypeError):  # empty payload, invalid base64, unsupported type, etc.
            # Optionally log something here
            return None

        if fit_foreground:
            if keep_aspect:
                # Fit while preserving aspect ratio, padding with transparency
                fg = ImageOps.contain(fg, bg.size)
            else:
                # Modern resample constant for Pillow >= 10.0.0
                fg = fg.resize(bg.size, resample=Image.Resampling.LANCZOS)
            position = (0, 0)

        # Copy background to avoid mutating the original image
        canvas = bg.copy()

        # Pasting with mask preserves alpha
        canvas.paste(fg, position, fg)

        return self._dump_image(
            canvas, out_format=format_output_img, return_base64=return_base64
        )
