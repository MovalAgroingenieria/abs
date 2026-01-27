# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import base64
import datetime as dt
import re
from datetime import date as date_type
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

import babel.dates
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from odoo import models, tools


class CommonFormat(models.AbstractModel):
    _name = "common.format"
    _description = (
        "Common helpers for locale-aware formatting (numbers, dates, etc.) "
        "and simple crypto utilities"
    )

    # ------------------------------ i18n ---------------------------------

    def _get_valid_lang_code(self, lang: Optional[str]) -> str:
        """Return a valid res.lang code, fallback to a safe default."""
        lang_code = lang or self.env.context.get("lang") or self.env.lang or "en_US"

        if not lang_code:
            return "en_US"

        if self.env["res.lang"].search_count([("code", "=", lang_code)]) > 0:
            return lang_code

        env_lang = self.env.lang or "en_US"
        if self.env["res.lang"].search_count([("code", "=", env_lang)]) > 0:
            return env_lang

        return "en_US"

    # ------------------------------ Numbers ------------------------------

    def transform_integer_to_locale(
        self, integer_number: int, lang: Optional[str] = None
    ) -> str:
        """Format an integer according to the active or provided language."""
        lang_code = self._get_valid_lang_code(lang)
        env_lang = self.env(context=dict(self.env.context, lang=lang_code))
        return tools.formatLang(env_lang, integer_number, digits=0, grouping=True)

    def transform_float_to_locale(
        self, float_number: float, precision: int, lang: Optional[str] = None
    ) -> str:
        """Format a float with a given precision respecting locale."""
        lang_code = self._get_valid_lang_code(lang)
        env_lang = self.env(context=dict(self.env.context, lang=lang_code))
        return tools.formatLang(env_lang, float_number, digits=precision, grouping=True)

    # ----------------------- Date format sanitization ----------------------

    def _sanitize_date_pattern(self, pattern: Optional[str]) -> str:
        """Return a CLDR date-only pattern safe for babel.format_date."""
        if not pattern:
            return "yyyy-MM-dd"

        pat = str(pattern).strip()

        if "%" in pat:
            mappings = {
                "%Y": "yyyy",
                "%y": "yy",
                "%m": "MM",
                "%d": "dd",
                "%b": "MMM",
                "%B": "MMMM",
                "%e": "d",
            }
            for key, val in mappings.items():
                pat = pat.replace(key, val)
            pat = re.sub(r"(%H|%I|%M|%S|%p)", "", pat)

        pat = re.sub(r"[HhmsaS]", "", pat)
        pat = re.sub(r"\s+", " ", pat)
        pat = re.sub(r"([/\-\.,:])\1+", r"\1", pat).strip()

        if not re.search(r"[yY].*[M].*[d]|[d].*[M].*[y]|[M].*[d].*[y]", pat):
            return "yyyy-MM-dd"
        return pat

    # ------------------------------- Dates -------------------------------

    def transform_date_to_locale(self, value: date_type, lang: Optional[str] = None) -> str:
        """Format a date using a sanitized pattern from res.lang when possible."""
        if not value:
            return ""

        lang_code = self._get_valid_lang_code(lang)

        fmt_db = None
        lang_rec = self.env["res.lang"].search([("code", "=", lang_code)], limit=1)
        if lang_rec:
            fmt_db = getattr(lang_rec, "date_format", None)

        fmt = self._sanitize_date_pattern(fmt_db)
        return babel.dates.format_date(value, format=fmt, locale=lang_code)

    # ---------------------------- Translations ---------------------------

    def get_value_from_translation(
        self, module: str, src: str, lang: Optional[str] = None
    ) -> str:
        """Return translated string for the given language, fallback to src.

        Note: Since Odoo 16, ir.translation is not available.
        """
        if src is None:
            return ""
        if not src:
            return src
        if not module:
            return src

        lang_code = self._get_valid_lang_code(lang)
        env_lang = self.env(context=dict(self.env.context, lang=lang_code))

        env_translate = getattr(env_lang, "_", None)
        if callable(env_translate):
            try:
                return env_translate(src, module=module)
            except TypeError:
                return env_translate(src)
            except Exception:  # noqa: BLE001
                return src

        return src

    # ------------------------------- Crypto ------------------------------

    def encrypt_data(self, params: Iterable[str], cipher_key: str) -> str:
        """Encrypt 'param1-param2-...' with AES-CBC (PKCS#7)."""
        credentials = "-".join(params).encode("utf-8")
        plaintext = pad(credentials, block_size=16, style="pkcs7")

        now_local = dt.datetime.now(ZoneInfo("Europe/Madrid"))
        iv_base = now_local.strftime("%Y-%m-%dT%H:%M")
        rounded_minute = "00" if now_local.minute < 30 else "30"
        iv_text = f"{iv_base[:14]}{rounded_minute}"
        iv = iv_text.encode("ascii")

        key = (cipher_key or "").encode("utf-8")
        cipher = AES.new(key, AES.MODE_CBC, iv)
        cipher_text = cipher.encrypt(plaintext)
        return base64.b64encode(cipher_text).decode("utf-8")

    # -------------------------- Human-friendly ---------------------------

    def get_date_as_text(
        self, value: Optional[date_type], with_year: bool = True, lang: Optional[str] = None
    ) -> str:
        """Return a human-readable date phrase in the chosen language."""
        if not value:
            return ""

        lang_code = self._get_valid_lang_code(lang)

        day = babel.dates.format_date(value, "d", locale=lang_code)
        month = babel.dates.format_date(value, "LLLL", locale=lang_code)
        year = babel.dates.format_date(value, "y", locale=lang_code) if with_year else ""

        if lang_code.endswith("_ES") or lang_code.startswith("es"):
            text = f"{day} de {month}"
            if year:
                text = f"{text} de {year}"
            return text

        text = f"{month} {day}"
        if year:
            text = f"{text}, {year}"
        return text

    # ----------------------------- HTML utils -----------------------------

    def is_html_field_filled(self, html_field: Optional[str]) -> bool:
        """Return True if the HTML contains any non-whitespace text."""
        if not html_field:
            return False
        return bool(tools.html2plaintext(html_field).strip())
