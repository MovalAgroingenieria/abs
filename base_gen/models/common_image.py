# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=too-many-arguments

import base64
import io
from typing import Optional, Tuple, Union

from odoo import models
from PIL import Image, ImageOps
from PIL.Image import DecompressionBombError

BinaryLike = Union[bytes, bytearray, str, io.BytesIO]
Point = Tuple[int, int]


class CommonImage(models.AbstractModel):
    _name = "common.image"
    _description = "Common helpers for image processing/compositing"

    # Hard safety limits to avoid memory/CPU bombs.
    # Adjust if your use case needs larger images.
    _max_pixels = 25_000_000  # ~25MP

    # ------------------------------- utils --------------------------------

    def _as_image(self, payload: BinaryLike) -> Image.Image:
        """Load a PIL Image from bytes / base64 str / BytesIO.

        Returns a detached RGBA image suitable for alpha compositing.
        """
        if payload is None:
            raise ValueError("Empty image payload.")

        buf: io.BytesIO
        if isinstance(payload, io.BytesIO):
            buf = payload
            buf.seek(0)
        elif isinstance(payload, (bytes, bytearray)):
            buf = io.BytesIO(payload)
        elif isinstance(payload, str):
            raw = payload.strip()

            # Support data URIs: data:image/png;base64,....
            if raw.startswith("data:") and "base64," in raw:
                raw = raw.split("base64,", 1)[1]

            try:
                buf = io.BytesIO(base64.b64decode(raw))
            except Exception as exc:  # noqa: BLE001
                raise ValueError("String payload is not valid base64.") from exc
        else:
            raise TypeError("Unsupported image payload type.")

        try:
            with Image.open(buf) as im:
                im.load()  # force decode to catch bombs early
                if im.width * im.height > self._max_pixels:
                    raise ValueError("Image too large.")
                return im.convert("RGBA").copy()
        except DecompressionBombError as exc:
            raise ValueError("Image payload rejected (decompression bomb).") from exc
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Unable to decode image payload.") from exc

    def _dump_image(
        self,
        image: Image.Image,
        out_format: str = "PNG",
        return_base64: bool = True,
        jpeg_background: Tuple[int, int, int] = (255, 255, 255),
    ) -> Union[bytes, str]:
        """Serialize a PIL Image to bytes/base64 for Odoo binary fields.

        - PNG/WebP support alpha; JPEG does not.
        - For JPEG, alpha is flattened over `jpeg_background`.
        """
        fmt = (out_format or "PNG").upper().strip()
        im = image

        if fmt in {"JPEG", "JPG"}:
            if im.mode in {"RGBA", "LA"}:
                bg = Image.new("RGB", im.size, jpeg_background)
                alpha = im.split()[-1]
                bg.paste(im.convert("RGBA"), mask=alpha)
                im = bg
            elif im.mode not in {"RGB", "L"}:
                im = im.convert("RGB")

        out = io.BytesIO()
        save_kwargs = {}
        if fmt in {"JPEG", "JPG"}:
            save_kwargs.update({"quality": 95, "subsampling": 0, "optimize": True})

        try:
            im.save(out, format=fmt, **save_kwargs)
        except TypeError:  # noqa: BLE001
            # Fallback to PNG for unsupported/invalid formats
            out = io.BytesIO()
            im.save(out, format="PNG")

        data = out.getvalue()
        if return_base64:
            return base64.b64encode(data).decode("ascii")
        return data

    @staticmethod
    def _center_position(container: Tuple[int, int], content: Tuple[int, int]) -> Point:
        """Return (x, y) to center content inside container."""
        cw, ch = container
        iw, ih = content
        return max((cw - iw) // 2, 0), max((ch - ih) // 2, 0)

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

        Returns None if inputs are missing or invalid.
        """
        if not background_img or not foreground_png:
            return None

        try:
            bg = self._as_image(background_img)
            fg = self._as_image(foreground_png)
        except (ValueError, TypeError):
            return None

        if fit_foreground:
            if keep_aspect:
                fitted = ImageOps.contain(fg, bg.size, method=Image.Resampling.LANCZOS)
                canvas_fg = Image.new("RGBA", bg.size, (0, 0, 0, 0))
                pos = self._center_position(bg.size, fitted.size)
                canvas_fg.paste(fitted, pos, fitted)
                fg = canvas_fg
            else:
                fg = fg.resize(bg.size, resample=Image.Resampling.LANCZOS)
            position = (0, 0)

        canvas = bg.copy()
        canvas.paste(fg, position, fg)

        return self._dump_image(
            canvas,
            out_format=format_output_img,
            return_base64=return_base64,
        )
