"""Read actual files while replaying path/descriptor timestamp differences."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from uwatch import evidence


_ABSENT = object()


def stat_view(info, *, ctime, birthtime=_ABSENT, **changes):
    fields = {name: getattr(info, name) for name in (
        "st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns")}
    fields["st_ctime_ns"] = ctime
    if birthtime is not _ABSENT:
        fields["st_birthtime_ns"] = birthtime
    fields.update(changes)
    return SimpleNamespace(**fields)


class FileIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="uwatch-file-identity-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "saved.csv"
        self.raw = b"account,amount\r\nSYNTHETIC,60\r\n"
        self.path.write_bytes(self.raw)
        self.info = self.path.lstat()

    def read_with(self, paths, descriptors):
        with patch.object(Path, "lstat", side_effect=paths), \
                patch.object(evidence.os, "fstat", side_effect=descriptors):
            return evidence._read_regular(self.path)

    def windows_views(self):
        # Windows CPython may expose creation time through lstat and change time
        # through fstat while both report the same explicit creation timestamp.
        path = stat_view(self.info, ctime=100, birthtime=100)
        descriptor = stat_view(self.info, ctime=200, birthtime=100)
        return path, descriptor

    def test_stable_saved_file_with_different_api_ctimes_is_admitted(self):
        path, descriptor = self.windows_views()
        first = self.read_with([path, path], [descriptor, descriptor])
        second = self.read_with([path, path], [descriptor, descriptor])
        self.assertEqual(first.raw, self.raw)
        self.assertEqual(first, second)
        self.assertEqual(self.path.read_bytes(), self.raw)

    def test_descriptor_change_during_read_is_still_refused(self):
        path, descriptor = self.windows_views()
        changed = stat_view(self.info, ctime=201, birthtime=100)
        with self.assertRaisesRegex(ValueError, "changed while reading"):
            self.read_with([path, path], [descriptor, changed])

    def test_path_change_during_read_is_still_refused(self):
        path, descriptor = self.windows_views()
        changed = stat_view(self.info, ctime=101, birthtime=100)
        with self.assertRaisesRegex(ValueError, "changed while reading"):
            self.read_with([path, changed], [descriptor, descriptor])

    def test_cross_api_creation_or_version_difference_is_refused(self):
        path, descriptor = self.windows_views()
        for field, value in (("st_birthtime_ns", 101), ("st_ino", self.info.st_ino + 1),
                             ("st_dev", self.info.st_dev + 1), ("st_size", self.info.st_size + 1),
                             ("st_mtime_ns", self.info.st_mtime_ns + 1)):
            with self.subTest(field=field):
                changed = SimpleNamespace(**vars(descriptor))
                setattr(changed, field, value)
                with self.assertRaisesRegex(ValueError, "changed while opening"):
                    self.read_with([path], [changed])

    def test_descriptor_change_between_admissions_retains_full_identity(self):
        path, descriptor = self.windows_views()
        first = self.read_with([path, path], [descriptor, descriptor])
        changed = stat_view(self.info, ctime=201, birthtime=100)
        second = self.read_with([path, path], [changed, changed])
        self.assertEqual(first.raw, second.raw)
        self.assertNotEqual(first, second)

    def test_legacy_stat_without_birthtime_keeps_ctime_comparison(self):
        stable = stat_view(self.info, ctime=100)
        self.assertEqual(self.read_with([stable, stable], [stable, stable]).raw, self.raw)
        changed = stat_view(self.info, ctime=101)
        with self.assertRaisesRegex(ValueError, "changed while opening"):
            self.read_with([stable], [changed])

    def test_real_resaved_file_is_read_without_changing_source(self):
        # No timestamp mocks: this also exercises the installed platform's APIs.
        self.path.write_bytes(self.raw)
        admitted = evidence._read_regular(self.path)
        self.assertEqual(admitted.raw, self.raw)
        self.assertEqual(self.path.read_bytes(), self.raw)

    def test_real_path_replacement_during_open_is_refused(self):
        replacement = self.path.with_name("replacement.csv")
        replacement.write_bytes(self.raw)
        original_open = os.open

        def replace_then_open(path, flags):
            replacement.replace(path)
            return original_open(path, flags)

        with patch.object(evidence.os, "open", side_effect=replace_then_open):
            with self.assertRaisesRegex(ValueError, "changed while opening"):
                evidence._read_regular(self.path)
        self.assertEqual(self.path.read_bytes(), self.raw)


if __name__ == "__main__":
    unittest.main()
