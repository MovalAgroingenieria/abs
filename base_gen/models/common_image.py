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
            return im.convert("RGBA").copy()

    def _dump_image(
        self,
        image: Image.Image,
        out_format: str = "PNG",
        return_base64: bool = True,
    ) -> Union[bytes, io.BytesIO, str]:
        """Serialize PIL Image to bytes/BytesIO/base64 for Odoo binary fields."""
        out = io.BytesIO()
        image.save(out, format=(out_format or "PNG").upper())
        data = out.getvalue()
        if return_base64:
            return base64.b64encode(data).decode("ascii")
        return data

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
        """Alpha-composite foreground over background.

        Args:
            background_img: bytes/base64/BytesIO of the background image.
            foreground_png: bytes/base64/BytesIO of the foreground (with alpha).
            format_output_img: output format (e.g. 'PNG', 'JPEG').
            position: (x, y) where the foreground's top-left corner is pasted.
            fit_foreground: if True, resize foreground to background size.
            keep_aspect: when fitting, preserve aspect ratio (letterbox/pad).
            return_base64: if True, return base64 string (best for Binary fields).

        Returns:
            base64 string (default) or raw bytes of the merged image.
            Returns None if any input is missing.

        Notes:
            - PNG is recommended to preserve transparency in the composite.
            - For JPEG output, transparency will be flattened against background.
        """
        if not background_img or not foreground_png:
            return None

        bg = self._as_image(background_img)  # RGBA
        fg = self._as_image(foreground_png)  # RGBA

        if fit_foreground:
            if keep_aspect:
                # Fit preserving aspect ratio, padding with transparency
                fg = ImageOps.contain(fg, bg.size)  # max-fit inside bg
            else:
                fg = fg.resize(bg.size, resample=Image.LANCZOS)
            position = (0, 0)

        # Create a copy to avoid mutating original
        canvas = bg.copy()

        # If position causes overflow, paste will clip automatically.
        # Use mask=fg to respect alpha channel
        canvas.paste(fg, position, fg)

        return self._dump_image(
            canvas, out_format=format_output_img, return_base64=return_base64
        )
