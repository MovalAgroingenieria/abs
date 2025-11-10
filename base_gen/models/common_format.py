# 2024 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import base64
import datetime as dt
from datetime import date as _date
from typing import Iterable, Optional

import babel
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from odoo import _, api, models, tools


class CommonFormat(models.AbstractModel):
    _name = "common.format"
    _description = (
        "Common helpers for locale-aware formatting (numbers, dates, etc.) "
        "and simple crypto utilities"
    )

    # ------------------------------ Numbers ------------------------------

    def transform_integer_to_locale(
        self, integer_number: int, lang: Optional[str] = None
    ) -> str:
        """Format an integer according to the active or provided language."""
        lang = lang or self.env.context.get("lang") or self.env.lang or "es_ES"
        # formatLang handles grouping and locale rules consistently
        return tools.formatLang(
            self.env, integer_number, digits=0, grouping=True, lang_code=lang
        )

    def transform_float_to_locale(
        self, float_number: float, precision: int, lang: Optional[str] = None
    ) -> str:
        """Format a float with a given precision respecting locale."""
        lang = lang or self.env.context.get("lang") or self.env.lang or "es_ES"
        # digits accepts either an int or a (digits, precision) tuple
        return tools.formatLang(
            self.env, float_number, digits=precision, grouping=True, lang_code=lang
        )

    # ------------------------------- Dates -------------------------------

    def transform_date_to_locale(self, value: _date, lang: Optional[str] = None) -> str:
        """Format a date object using the language's date_format."""
        if not value:
            return ""
        lang_code = lang or self.env.context.get("lang") or self.env.lang or "es_ES"
        lang_rec = self.env["res.lang"].search([("code", "=", lang_code)], limit=1)
        fmt = (
            lang_rec.date_format if lang_rec and lang_rec.date_format else "yyyy-MM-dd"
        )
        # value is a date object; format_date expects a date and a CLDR pattern
        return babel.dates.format_date(value, format=fmt, locale=lang_code)

    # ---------------------------- Translations ---------------------------

    def get_value_from_translation(
        self, module: str, src: str, lang: Optional[str] = None
    ) -> str:
        """Return the translated value for (module, src, lang) if present, else src."""
        lang_code = lang or self.env.context.get("lang") or self.env.lang
        if not lang_code:
            return src
        tr = (
            self.sudo()
            .env["ir.translation"]
            .search(
                [("lang", "=", lang_code), ("module", "=", module), ("src", "=", src)],
                limit=1,
            )
        )
        return tr.value or src

    # ------------------------------- Crypto ------------------------------

    def encrypt_data(self, params: Iterable[str], cipher_key: str) -> str:
        """Encrypt 'param1-param2-...' with AES-CBC.

        Notes:
        - Uses PKCS#7 padding (block=16).
        - IV is 16-byte ASCII based on Europe/Madrid time rounded to :00 or :30.
          This keeps your legacy behavior but with correct block handling.
        - 'cipher_key' must be 16/24/32 bytes long (AES-128/192/256).

        Returns:
            Base64-encoded ciphertext (str).
        """
        # Build plaintext
        credentials = "-".join(params).encode("utf-8")
        plaintext = pad(credentials, block_size=16, style="pkcs7")

        # IV: 'YYYY-MM-DDTHH:MM' -> 16 chars; round minutes to 00/30
        now_utc = dt.datetime.utcnow().replace(tzinfo=tools.UTC)
        now_local = tools.datetime_to_string(
            tools.convert_utc_to_tz(now_utc, "Europe/Madrid")
        )
        # now_local like 'YYYY-MM-DD HH:MM:SS'; normalize to 'YYYY-MM-DDTHH:MM'
        iv_base = (now_local[:16]).replace(" ", "T")
        minute = int(iv_base[14:16])
        rounded_minute = "00" if minute < 30 else "30"
        iv_text = iv_base[:14] + rounded_minute  # 16 chars
        iv = iv_text.encode("utf-8")

        # Key must be a valid AES length (16/24/32). Let Crypto raise if not.
        key = cipher_key.encode("utf-8")

        cipher = AES.new(key, AES.MODE_CBC, iv)
        cipher_text = cipher.encrypt(plaintext)
        return base64.b64encode(cipher_text).decode("utf-8")

    # -------------------------- Human-friendly ---------------------------

    def get_date_as_text(
        self, value: Optional[_date], with_year: bool = True, lang: Optional[str] = None
    ) -> str:
        """Return a human-readable date phrase in the chosen language.

        ES example: '10 de enero de 2025'
        EN example: 'January 10, 2025'

        This keeps your legacy behavior but fixes control flow and defaults.
        """
        if not value:
            return ""
        lang_code = lang or self.env.context.get("lang") or self.env.lang or "es_ES"

        # Day & month names via Babel ensure locale correctness
        day = babel.dates.format_date(value, "d", locale=lang_code)
        month = babel.dates.format_date(value, "LLLL", locale=lang_code)
        year = (
            babel.dates.format_date(value, "y", locale=lang_code) if with_year else ""
        )

        # Spanish-like locales: use 'de' separators
        if lang_code.endswith("_ES") or lang_code.startswith("es"):
            # Use translation for 'of' in case you localize to other romance langs
            # e.g., _('of') could be mapped if you maintain i18n terms.
            text = f"{day} {_('of')} {month}"
            if year:
                text = f"{text} {_('of')} {year}"
            return text

        # Default English-like phrase
        # Note: Babel can do ordinals, but we keep your original simple 'day' form.
        text = f"{month} {day}"
        if with_year and year:
            text = f"{text}, {year}"
        return text

    # ----------------------------- HTML utils -----------------------------

    def is_html_field_filled(self, html_field: Optional[str]) -> bool:
        """Return True if the HTML contains any non-whitespace text."""
        if not html_field:
            return False
        return bool(tools.html2plaintext(html_field).strip())
