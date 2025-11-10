# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=protected-access
# pylint: disable=too-many-arguments

from contextlib import contextmanager

# Odoo test base
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


from odoo import exceptions

# ------------------------------ test helpers ------------------------------


class _FakeEnv:
    """Tiny env that only provides _() i18n formatting."""

    def _(self, msg, *args):
        return msg % args if args else msg


class _FakeRecord:
    """Single fake record mirroring the attributes used by SimpleModel methods."""

    def __init__(
        self,
        *,
        # flags (class-level in real model, we set on record for tests)
        set_num_code=False,
        set_alphanum_code_to_lowercase=False,
        set_alphanum_code_to_uppercase=False,
        size_name=30,
        size_description=75,
        allowed_blanks_in_code=True,
        minlength=0,
        maxlength=0,
        # field values
        alphanum_code="",
        num_code=0,
        description="",
    ):
        self.set_num_code = set_num_code
        self.set_alphanum_code_to_lowercase = set_alphanum_code_to_lowercase
        self.set_alphanum_code_to_uppercase = set_alphanum_code_to_uppercase
        self.size_name = size_name
        self.size_description = size_description
        self.allowed_blanks_in_code = allowed_blanks_in_code
        self.minlength = minlength
        self.maxlength = maxlength

        self.alphanum_code = alphanum_code
        self.num_code = num_code
        self.description = description

        # outputs computed
        self.name = None
        self.display_name = None

        # env for i18n in constraints
        self.env = _FakeEnv()


class _FakeRecordset:
    """An iterable holding exactly one fake record, like an Odoo recordset of 1."""

    def __init__(self, rec: _FakeRecord):
        self._rec = rec

    def __iter__(self):
        yield self._rec


@contextmanager
def _patch_model_attrs(recordset, **overrides):
    """
    Temporarily patch CLASS-LEVEL attributes on an Odoo model.

    We write to recordset.__class__ to avoid read-only recordset attrs.
    """
    target_cls = recordset if isinstance(recordset, type) else recordset.__class__
    originals = {}
    try:
        for k, v in overrides.items():
            originals[k] = getattr(target_cls, k)
            setattr(target_cls, k, v)
        yield
    finally:
        for k, v in originals.items():
            setattr(target_cls, k, v)


# --------------------------------- tests ---------------------------------


@tagged("-at_install", "post_install")
class TestSimpleModel(SavepointCase):
    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        super().setUpClass()
        cls.SM = cls.env["simple.model"]  # abstract model recordset

    # ----------------------- _process_alphanum_code -----------------------

    def test_process_alphanum_code_trim_and_lower(self):
        with _patch_model_attrs(
            self.SM,
            size_name=5,
            set_alphanum_code_to_lowercase=True,
            set_alphanum_code_to_uppercase=False,
        ):
            out = self.SM._process_alphanum_code("ABCdefGH")
            self.assertEqual(out, "abcde")

    def test_process_alphanum_code_trim_and_upper(self):
        with _patch_model_attrs(
            self.SM,
            size_name=4,
            set_alphanum_code_to_lowercase=False,
            set_alphanum_code_to_uppercase=True,
        ):
            out = self.SM._process_alphanum_code("abCdEf")
            self.assertEqual(out, "ABCD")

    # ------------------------------ _compute_name ------------------------

    def test_compute_name_numeric_mode(self):
        # Call the bound method but feed a fake recordset
        fn = self.SM.__class__._compute_name
        rec = _FakeRecord(set_num_code=True, size_name=6, num_code=42)
        rs = _FakeRecordset(rec)
        fn(rs)  # mutates rec.name
        self.assertEqual(rec.name, "000042")

    def test_compute_name_alphanum_mode(self):
        fn = self.SM.__class__._compute_name
        rec = _FakeRecord(set_num_code=False, size_name=3, alphanum_code="ZXCV")
        rs = _FakeRecordset(rec)
        fn(rs)
        self.assertEqual(rec.name, "ZXC")

    # ------------------------- _compute_display_name ---------------------

    def test_compute_display_name_numeric_mode(self):
        fn = self.SM.__class__._compute_display_name
        rec = _FakeRecord(set_num_code=True, description="Desc", num_code=7)
        rs = _FakeRecordset(rec)
        fn(rs)
        self.assertEqual(rec.display_name, "Desc [7]")

    def test_compute_display_name_alphanum_mode(self):
        fn = self.SM.__class__._compute_display_name
        rec = _FakeRecord(set_num_code=False, alphanum_code="abc123")
        rs = _FakeRecordset(rec)
        fn(rs)
        self.assertEqual(rec.display_name, "abc123")

    # --------------------------- _check_alphanum_code --------------------

    def test_check_alphanum_code_forbid_blanks(self):
        fn = self.SM.__class__._check_alphanum_code
        rec = _FakeRecord(allowed_blanks_in_code=False, alphanum_code="AA BB")
        rs = _FakeRecordset(rec)
        with self.assertRaises(exceptions.ValidationError):
            fn(rs)

    def test_check_alphanum_code_minlength_maxlength(self):
        fn = self.SM.__class__._check_alphanum_code

        # Too short
        rec_short = _FakeRecord(minlength=3, maxlength=5, alphanum_code="AB")
        with self.assertRaises(exceptions.ValidationError):
            fn(_FakeRecordset(rec_short))

        # Too long
        rec_long = _FakeRecord(minlength=3, maxlength=5, alphanum_code="ABCDEF")
        with self.assertRaises(exceptions.ValidationError):
            fn(_FakeRecordset(rec_long))

        # Valid
        rec_ok = _FakeRecord(minlength=3, maxlength=5, alphanum_code="ABCD")
        # Should not raise
        fn(_FakeRecordset(rec_ok))

    # ------------------- _get_sequence + _default_alphanum_code ----------

    def test_get_sequence_and_default_alphanum_code(self):
        """
        Configure an ir.sequence via ir.config_parameter and ensure:
        - _get_sequence retrieves it
        - _default_alphanum_code previews the next without consuming it
        """
        seq = self.env["ir.sequence"].create(
            {
                "name": "Test SimpleModel Seq",
                "implementation": "no_gap",
                "prefix": "S-",
                "padding": 4,
            }
        )
        key = "test.simple.model.sequence.id"
        self.env["ir.config_parameter"].sudo().set_param(key, str(seq.id))

        # Patch class-level attr to point to our param
        with _patch_model_attrs(self.SM, sequence_for_codes=key):
            fetched = self.SM._get_sequence(self.SM.sequence_for_codes)
            self.assertTrue(fetched)
            self.assertEqual(fetched.id, seq.id)

            preview1 = self.SM._sequence_preview_next(fetched)
            # default should return same preview
            self.assertEqual(self.SM._default_alphanum_code(), preview1)

            # Ensure preview did NOT consume the sequence
            preview2 = self.SM._sequence_preview_next(fetched)
            self.assertEqual(preview2, preview1)
