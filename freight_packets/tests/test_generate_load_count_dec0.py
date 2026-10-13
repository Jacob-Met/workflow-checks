"""Real generate CLI regression for negative sample load counts."""
import csv
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
MODE = [] if __debug__ else ["-O"]


def snapshot(root):
    if not root.exists():
        return None
    result = {}
    for path in sorted(root.rglob("*")):
        info = path.stat()
        key = path.relative_to(root).as_posix()
        result[key] = (stat.S_IMODE(info.st_mode), info.st_mtime_ns,
                       hashlib.sha256(path.read_bytes()).hexdigest()
                       if path.is_file() else None)
    return result


class GenerateLoadCountTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.calls = 0

    def generate(self, output, *args):
        command = [sys.executable, *MODE, "-B", "-m", "freightpkt",
                   "generate", "--out", str(output), *args]
        run = subprocess.run(command, cwd=SOURCE, capture_output=True, timeout=20)
        self.calls += 1
        artifacts = os.environ.get("FREIGHT_COUNT_TEST_ARTIFACTS")
        if artifacts:
            dest = Path(artifacts) / (self._testMethodName + "-" + str(self.calls))
            dest.mkdir(parents=True, exist_ok=False)
            (dest / "stdout.bin").write_bytes(run.stdout)
            (dest / "stderr.bin").write_bytes(run.stderr)
            (dest / "command.json").write_text(json.dumps(
                {"argv": command, "cwd": str(SOURCE), "exit": run.returncode},
                indent=2) + "\n", encoding="utf-8")
        return run

    def assert_refused(self, run):
        self.assertEqual(run.returncode, 2)
        self.assertEqual(run.stdout, b"")
        self.assertIn(b"--loads must be nonnegative", run.stderr)
        self.assertNotIn(b"Traceback", run.stderr)

    def test_negative_count_creates_no_destination(self):
        output = self.root / "missing-parent" / "data"
        run = self.generate(output, "--loads=-1")
        self.assertFalse(output.parent.exists(), "negative count created directories")
        self.assert_refused(run)

    def test_negative_count_preserves_existing_fixture(self):
        output = self.root / "existing"
        (output / "ratecons").mkdir(parents=True)
        (output / "loads.csv").write_bytes(b"load_id,customer\r\nKEPT,FICTIONAL\r\n")
        (output / "expected.json").write_bytes(b'{"retained":"fictional"}\n')
        (output / "ratecons" / "kept.txt").write_bytes(b"retained fictional terms\n")
        before = snapshot(output)
        run = self.generate(output, "--loads", "-17", "--seed", "11")
        self.assertEqual(snapshot(output), before, "negative count rewrote the fixture")
        self.assert_refused(run)

    def test_zero_and_two_load_content_matches_retained_originals(self):
        expected = ORIGINAL_HASHES
        for count in (0, 2):
            with self.subTest(count=count):
                output = self.root / str(count)
                run = self.generate(output, "--loads", str(count), "--seed", "7")
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(run.stderr, b"")
                actual = {p.relative_to(output).as_posix():
                          hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                          for p in output.rglob("*") if p.is_file()}
                self.assertEqual(actual, expected[str(count)])
                with (output / "loads.csv").open(newline="", encoding="utf-8") as stream:
                    self.assertEqual(len(list(csv.DictReader(stream))), count)
                self.assertIn((": " + str(count) + " loads,").encode(), run.stdout)

    def test_default_count_still_generates_twenty_four_loads(self):
        output = self.root / "default"
        run = self.generate(output, "--seed", "7")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stderr, b"")
        with (output / "loads.csv").open(newline="", encoding="utf-8") as stream:
            self.assertEqual(len(list(csv.DictReader(stream))), 24)
        answer = json.loads((output / "expected.json").read_bytes())
        self.assertEqual(len(answer["stops"]), 48)
        self.assertIn(b": 24 loads,", run.stdout)


# Full UTF-8 file content from the original probe; normalize CRLF for platform text writes.
ORIGINAL_HASHES = {'0': {'fines_schedule.csv': '86cf306c2ca02ea06f629ab002e22e77fbd5351fad77cc3177dc9b8774b9b72a', 'telematics.csv': 'a988a979f71bc6836ab518611a1a61d2bc411be9b68e133a38682d4a056e75d0', 'carrier_invoices.csv': 'cd7e625761a6f145d444b880598b5ff8b5a1111ee7f5ac03c373812f7921de6d', 'tracking_stops.csv': '49f83f8de8869b4e4ee871aa2d6689af460d6d5b7f5c33b65df4511a10d8ae5a', 'loads.csv': '4d593cac6cd370041660921ffc73194b45b7d16bcedbd9331d473b4f53186d96', 'documents.csv': '55cac43d402d07c6d18a2bc501cf84939a0ae31fea9e7c21ff41bd1709a6db6e', 'disputes.csv': 'e7d2725476b766ee2561a076a52ed720e16f3d3e3b7dd68cf41f24f7a52ff87a', 'README_SYNTHETIC.txt': '618c294869b73ef0a74771bd5e9bef65225b33b251ad394c3a91275b8fcf3616', 'expected.json': '3986c23b78264bdc1e2908f16fb8ef34aabcf67fd685dc6b58a9fb2e5143074c', 'telematics_extra.json': '53a9e04b617884af42c3d866a532af6fa99122967d87558438e2741fee95f3dc'}, '2': {'fines_schedule.csv': '86cf306c2ca02ea06f629ab002e22e77fbd5351fad77cc3177dc9b8774b9b72a', 'telematics.csv': 'd689e75e50e7085b4cfa4af347cb792423b5c32089bf7d062aa248d60dd3ba31', 'carrier_invoices.csv': '4648f37f94723794f4e1f13fe66263d83214c1e3da50af1157064624be2dc93a', 'tracking_stops.csv': '0772464bacc802d17fccda7c9ee044ebf1ba6cd9b6aa45083d3c52451d338fc2', 'loads.csv': '2f5e09a6ab5ba72f7c3315b2040b69fa7fec47e853ad68a2815736f830d6392d', 'documents.csv': '76175c9591995d8036b5e815193371bf9c27774397beba558dda5df7bfe13501', 'disputes.csv': 'e7d2725476b766ee2561a076a52ed720e16f3d3e3b7dd68cf41f24f7a52ff87a', 'README_SYNTHETIC.txt': '618c294869b73ef0a74771bd5e9bef65225b33b251ad394c3a91275b8fcf3616', 'expected.json': '7a8c296d4136b374baeb9f51f0937a23f69989b35e9811b99478f0cbd2a5c9ce', 'telematics_extra.json': '89ff8f95186d3844296fbe57634bb05c99b1a1958383f4ac85fa6e43f1fad517', 'ratecons/RC-48001.txt': '6516601927e2683ffce7df2cdba6eae14a6aae7a39b8be77739b99a42a6c7148', 'ratecons/RC-48000.txt': 'cfc46fde355277cea67a6465845897935f843ccf63f183e7ea78028e0f440e2a'}}


if __name__ == "__main__":
    unittest.main()
