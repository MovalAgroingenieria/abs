# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import base64
import datetime as dt
import re
from datetime import date as _date
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

import babel
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from odoo import models, tools, _

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
        # Pass language through context; formatLang reads it from env.context
        env_lang = self.env(context=dict(self.env.context, lang=lang))
        return tools.formatLang(env_lang, integer_number, digits=0, grouping=True)

    def transform_float_to_locale(
            self, float_number: float, precision: int, lang: Optional[str] = None
    ) -> str:
        """Format a float with a given precision respecting locale."""
        lang = lang or self.env.context.get("lang") or self.env.lang or "es_ES"
        env_lang = self.env(context=dict(self.env.context, lang=lang))
        # digits can be an int for decimal places in v18
        return tools.formatLang(env_lang, float_number, digits=precision, grouping=True)

    # --- helper to sanitize/normalize a date-only pattern for Babel (CLDR) ---
    def _sanitize_date_pattern(self, pattern: Optional[str]) -> str:
        """Return a CLDR date-only pattern safe for babel.format_date.

        - Strips time tokens if present (H, h, m, s, S, a).
        - Converts common strftime directives (%d/%m/%Y etc.) to CLDR.
        - Falls back to a safe default when the input is empty or unusable.
        """
        if not pattern:
            return "yyyy-MM-dd"

        pat = str(pattern).strip()

        # If it looks like strftime (has %), map the most common tokens to CLDR
        if "%" in pat:
            mappings = {
                r"%Y": "yyyy",
                r"%y": "yy",
                r"%m": "MM",
                r"%d": "dd",
                r"%b": "MMM",
                r"%B": "MMMM",
                r"%e": "d",  # day without leading zero
            }
            for k, v in mappings.items():
                pat = pat.replace(k, v)
            # Remove time-related directives if any slipped in
            pat = re.sub(r"(%H|%I|%M|%S|%p)", "", pat)

        # Strip CLDR time tokens if present
        # (H/h = hour, m = minute, s/S = seconds/fraction, a = am/pm)
        pat = re.sub(r"[HhmsaS]", "", pat)

        # Collapse duplicate separators that may result from stripping
        pat = re.sub(r"\s+", " ", pat)
        pat = re.sub(r"([/\-\.,:])\1+", r"\1", pat).strip()

        # Ensure we still have a date-like pattern; else return a safe default
        if not re.search(r"[yY].*[M].*[d]|[d].*[M].*[y]|[M].*[d].*[y]", pat):
            return "yyyy-MM-dd"
        return pat

    # ------------------------------- Dates -------------------------------

    def transform_date_to_locale(self, value: _date, lang: Optional[str] = None) -> str:
        """Format a date object using a sanitized, date-only pattern per language."""
        if not value:
            return ""
        lang_code = lang or self.env.context.get("lang") or self.env.lang or "es_ES"

        # Try to read res.lang; be defensive across setups
        fmt_db = None
        try:
            lang_rec = self.env["res.lang"].search([("code", "=", lang_code)], limit=1)
            if lang_rec:
                fmt_db = getattr(lang_rec, "date_format", None)
        except Exception:  # pylint: disable=broad-exception-caught
            fmt_db = None

        fmt = self._sanitize_date_pattern(fmt_db)
        return babel.dates.format_date(value, format=fmt, locale=lang_code)

    # ---------------------------- Translations ---------------------------

    def get_value_from_translation(
            self, module: str, src: str, lang: Optional[str] = None
    ) -> str:
        """Return the translated value for (module, src, lang) if present, else src.

        Uses Odoo v18's standard translation mechanism.
        """
        # Handle None source
        if src is None:
            return ""

        # Get language code
        lang_code = lang or self.env.context.get("lang") or self.env.lang or "en_US"

        # Early return for invalid inputs
        if not lang_code or not module or not src:
            return src

        try:
            # In Odoo v18, the standard way is to use _(source) with language context
            # Create a new environment with the desired language
            ctx = dict(self.env.context, lang=lang_code) if self.env.context else {'lang': lang_code}
            env_with_lang = self.env(context=ctx)

            # Get translation using standard _() function
            # Odoo's translation system will handle module context automatically
            translated = env_with_lang._(src)

            # If no translation found, it returns the original string
            return translated

        except Exception:
            # Fallback to original string on any error
            return src

    # ------------------------------- Crypto ------------------------------

    def encrypt_data(self, params: Iterable[str], cipher_key: str) -> str:
        """Encrypt 'param1-param2-...' with AES-CBC.

        - PKCS#7 padding (block=16).
        - IV: Europe/Madrid time redondeada a :00 / :30 ->
        16 bytes ASCII 'YYYY-MM-DDTHH:MM'.
        - 'cipher_key' de 16/24/32 bytes (AES-128/192/256).
        """
        # Plaintext con padding PKCS#7
        credentials = "-".join(params).encode("utf-8")
        plaintext = pad(credentials, block_size=16, style="pkcs7")

        # Hora local Europe/Madrid sin depender de odoo.tools
        now_local = dt.datetime.now(ZoneInfo("Europe/Madrid"))
        # Base 'YYYY-MM-DDTHH:MM'
        iv_base = now_local.strftime("%Y-%m-%dT%H:%M")
        minute = now_local.minute
        rounded_minute = "00" if minute < 30 else "30"
        # Construir IV de 16 bytes ASCII
        iv_text = f"{iv_base[:14]}{rounded_minute}"  # YYYY-MM-DDTHH: + MM
        iv = iv_text.encode("ascii")  # 16 bytes exactos

        key = cipher_key.encode("utf-8")  # dejar que Crypto valide tamaño

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
            # Use the new translation method
            of_translation = self.get_value_from_translation("base", "de", lang_code)
            if of_translation == "de":  # Fallback if not found
                of_translation = "de"

            text = f"{day} {of_translation} {month}"
            if year:
                text = f"{text} {of_translation} {year}"
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