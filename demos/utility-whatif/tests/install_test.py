import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

INSTALLER = Path(__file__).resolve().parents[1] / "install.py"


class InstallationTests(unittest.TestCase):
    def command(self, action, target):
        return subprocess.run([sys.executable, str(INSTALLER), action, "--target", str(target)], capture_output=True, text=True)

    def test_install_rollback_reinstall_exact_readback(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "installed"
            first = self.command("install", target)
            self.assertEqual(first.returncode, 0, first.stderr)
            expected = json.loads(first.stdout)["manifest"]["files"]
            self.assertEqual(self.command("readback", target).returncode, 0)
            self.assertEqual(self.command("rollback", target).returncode, 0)
            self.assertFalse(target.exists())
            second = self.command("install", target)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(json.loads(second.stdout)["manifest"]["files"], expected)
            self.assertEqual(self.command("readback", target).returncode, 0)

    def test_existing_target_is_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "existing"
            target.mkdir()
            (target / "important.txt").write_text("retain")
            self.assertNotEqual(self.command("install", target).returncode, 0)
            self.assertEqual((target / "important.txt").read_text(), "retain")

    def test_changed_and_unexpected_files_block_rollback(self):
        for changed in (True, False):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as root:
                target = Path(root) / "installed"
                self.assertEqual(self.command("install", target).returncode, 0)
                path = target / ("index.html" if changed else "unrelated.txt")
                path.write_text("preserve this edit")
                self.assertNotEqual(self.command("rollback", target).returncode, 0)
                self.assertEqual(path.read_text(), "preserve this edit")
                self.assertTrue((target / "fixture.json").exists())

    def test_redirected_file_blocks_readback_and_rollback(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "installed"
            self.assertEqual(self.command("install", target).returncode, 0)
            external = Path(root) / "outside.txt"
            external.write_text("external")
            (target / "index.html").unlink()
            (target / "index.html").symlink_to(external)
            self.assertNotEqual(self.command("readback", target).returncode, 0)
            self.assertNotEqual(self.command("rollback", target).returncode, 0)
            self.assertEqual(external.read_text(), "external")


if __name__ == "__main__":
    unittest.main()
